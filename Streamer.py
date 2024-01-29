##The server host is the one that will be sending the video to the client
##The server client is the one that will be recieving the video stream from the host

import cv2
from cv2 import EVENT_MOUSEMOVE
import pyautogui
import numpy as np

from PIL import Image as im
import win32gui
from os import path

import socket
import pickle
import struct
import threading

import os

from screeninfo import get_monitors

#set up for multi screen grab
from PIL import ImageGrab
from functools import partial
ImageGrab.grab = partial(ImageGrab.grab,all_screens=True)

from tkinter import *

resolutions = [(640,480),(1280,720),(1920,1080),(2560,1440),(3840,2160),(7680,4320)]

trace = False#debug tracer
allowed = 1#allowed connections to the host server from clients
serverTimeout = 600
masterWinDo = 'Host Computer'
streamingResolution = resolutions[1]

class StreamerServer:
    def __init__(self, host,port):
        self.host = host
        self.port = port

        self.running = False
        self.block = threading.Lock()
        self.connections = 0
        self.available=allowed

        self.configureEncoding()
        
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.settimeout(serverTimeout)
        self.socketInit()
        print("Server Initialized" if trace else "",end="")

    def serverStart(self):
        if self.running:
            print("Server alreading active")
        else:
            self.running = True
            print("Server Starting..." if trace else "",end="")
            serverThread = threading.Thread(target=self.manageConnections)
            serverThread.start()

    def serverStop(self):
        if self.running:
            self.running = False
            print("Server Stop Requested..." if trace else "",end="")
            print("Server Terminated")
            os._exit(1)
        else:
            print("Server already closed")

    def configureEncoding(self):
        self.encodingParams = [int(cv2.IMWRITE_JPEG_QUALITY),90]

    def socketInit(self):
        self.sock.bind((self.host,self.port))

    def manageConnections(self):
        print("Confirming Connection Statuses" if trace else "",end="")
        self.sock.listen()
        print("Server Activated")
        while self.running:
            print("Connection Manager..." if trace else "",end="")
            self.block.acquire()
            connection, address = self.sock.accept()
            print("Connection Attempt Acknowledged by Server" if trace else "",end="")
            if self.connections >= self.available:
                print("Too many connections")
                connection.close()
                self.block.release()
                continue
            else:
                print("Adding connection" if trace else "",end="")
                self.connections += 1
            self.block.release()
            thread = threading.Thread(target=self.hostSender,args=(connection,address))
            thread.start()

    def getFrame(self):
        return None
    
    def cleanUp(self):
        cv2.destroyAllWindows()
        print("Sender Cleaned cv2 Window" if trace else "",end="")

    def hostSender(self,connection,address):
        print("Starting Stream..." if trace else "",end="")
        while self.running:
            frame = self.getFrame()
            result, frame = cv2.imencode('.jpg',frame,self.encodingParams)
            data = pickle.dumps(frame,0)
            size = len(data)

            try:
                connection.sendall(struct.pack('>L',size) + data)
            except ConnectionResetError:
                print("Connection Reset Error" if trace else "",end="")
                self.running = False
            except ConnectionAbortedError:
                print("Connection Aborted Error" if trace else "",end="")
                self.running = False
            except BrokenPipeError:
                print("Broken Pipe Error" if trace else "",end="")
                self.running = False
        print("Client Disconnected" if trace else "",end="")
        print("Removing Connection" if trace else "",end="")
        self.connections -= 1
        connection.close()
        
        self.cleanUp()

        self.serverStop()
        self.serverStart()


class StreamerClient:
    def __init__(self,host,port):
        self.host = host
        self.port = port

        self.quit = 'q'

        self.running = False
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    def startClient(self):
        if self.running:
            print("Client already active")
        else:
            self.running = True
            print("Connecting to server..." if trace else "",end="")
            try:
                self.sock.connect((self.host,self.port))
            except TimeoutError:
                print("Server Connection Timed Out")
                self.stopClient()
            print("Connected to Server")
            clientThread = threading.Thread(target=self.clientReciever)
            clientThread.start()

    def stopClient(self):
        if self.running:
            print("Terminated Client" if trace else "",end="")
            self.running = False
            os._exit(1)
        else:
            print("Client already closed")

    def clientReciever(self):
        payloadSize = struct.calcsize('>L')
        data = b""

        try:
            while self.running:
                breakLoop = False
                while len(data) < payloadSize:
                    recieved = (self.sock).recv(4096)
                    if recieved == b'':
                        self.sock.close()
                        self.breakLoop = True
                        break
                    data += recieved
                if breakLoop:
                    break

                packedMsgSize = data[:payloadSize]
                data = data[payloadSize:]

                msgSize = struct.unpack(">L",packedMsgSize)[0]

                while len(data) < msgSize:
                    data += self.sock.recv(4096)
                
                frameData = data[:msgSize]
                data = data[msgSize:]

                cv2.namedWindow(masterWinDo,cv2.WINDOW_KEEPRATIO)

                frame = pickle.loads(frameData,fix_imports=True,encoding="bytes")
                frame = cv2.imdecode(frame,cv2.IMREAD_COLOR)
                
                cv2.imshow(masterWinDo,frame)
                
                if cv2.waitKey(1) == ord(self.quit):#close on 'q' key toggle
                    pass#do nothing on quit key

                if not (cv2.getWindowProperty(masterWinDo,cv2.WND_PROP_VISIBLE) >= 1):#close on 'x' toggle by mouse
                    self.sock.close()
                    self.stopClient()
                    break
                


        except ConnectionResetError:
            print("Server Terminated: Connection Ended")
            self.stopClient()
        # except Exception as e:
        #     print("Server Connection Error",type(e))
        #     self.stopClient()

class HostStreamer(StreamerServer):
    def __init__(self,host,port):
        self.res = streamingResolution

        super(HostStreamer,self).__init__(host,port)
    def getFrame(self):
        screenXs = []
        screenYs = []
        for m in get_monitors():
            if not m.is_primary:
                screenXs.append(m.x)
                screenYs.append(m.y)

        #TODO: Add ability to select single or all monitors...need to change offset of mouse position
        screen = pyautogui.screenshot()


        frame = np.array(screen)
    
        x,y = pyautogui.position()
        if len(get_monitors()) > 1:
            x = x + abs(min(screenXs))
            y = y + abs(min(screenYs))

        cursor = [
            [#regular
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,2,2,1,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,2,2,2,1,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,2,2,2,2,1,0,0,0,0,0,0,0],
                [1,2,2,2,2,2,2,1,1,1,1,1,0,0,0,0,0,0,0],
                [1,2,2,2,1,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,1,0,1,2,2,1,0,0,0,0,0,0,0,0,0,0],
                [1,2,1,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0,0],
                [1,1,0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0]
            ],[#inverted
                [2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,2,0,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,2,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,1,2,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,1,1,2,0,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,1,1,1,2,0,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,1,1,1,1,2,0,0,0,0,0,0,0],
                [2,1,1,1,1,1,1,2,2,2,2,2,0,0,0,0,0,0,0],
                [2,1,1,1,2,1,1,2,0,0,0,0,0,0,0,0,0,0,0],
                [2,1,1,2,0,2,1,1,2,0,0,0,0,0,0,0,0,0,0],
                [2,1,2,0,0,2,1,1,2,0,0,0,0,0,0,0,0,0,0],
                [2,2,0,0,0,0,2,1,1,2,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,2,1,1,2,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,2,2,0,0,0,0,0,0,0,0,0,0]
            ],[#finger
                [0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,2,2,1,1,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,2,2,1,2,2,1,1,1,0,0,0,0,0,0],
                [1,1,1,0,1,2,2,1,2,2,1,2,2,1,1,0,0,0,0],
                [1,2,2,0,1,2,2,0,2,2,0,2,2,1,2,0,1,0,0],
                [1,2,2,1,1,2,2,1,2,2,1,2,2,1,2,1,0,0,0],
                [0,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,0,0],
                [0,0,1,2,2,2,2,2,2,2,2,2,2,2,2,2,1,0,0],
                [0,0,1,2,2,2,2,2,2,2,2,2,2,2,2,2,1,0,0],
                [0,0,0,1,2,2,2,2,2,2,2,2,2,2,2,2,1,0,0],
                [0,0,0,1,2,2,2,2,2,2,2,2,2,2,2,1,0,0,0],
                [0,0,0,0,1,2,2,2,2,2,2,2,2,2,2,1,0,0,0],
                [0,0,0,0,1,2,2,2,2,2,2,2,2,2,2,1,0,0,0],
                [0,0,0,0,0,1,2,2,2,2,2,2,2,2,1,0,0,0,0],
                [0,0,0,0,0,1,2,2,2,2,2,2,2,2,1,0,0,0,0],
                [0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0,0]
            ],[#bar
                [0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0],
                [0,0,0,0,2,2,2,2,2,1,2,2,2,2,2,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,1,1,1,1,1,2,1,1,1,1,0,0,0,0],
                [0,0,0,0,2,2,2,2,2,2,2,2,2,2,2,0,0,0,0]
            ],[#up/down arrow
                [0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,2,0,1,0,0,0,0,0,0],
                [0,0,0,0,0,1,1,1,1,2,1,1,1,1,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,1,1,1,1,2,1,1,1,1,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,2,2,1,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0]
            ],[#topleft/bottomright arrow
                [1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,1,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [1,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,1],
                [0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,1,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1]
            ],[#left/right arrow
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0,0],
                [0,0,0,1,1,0,0,0,0,0,0,0,0,0,1,1,0,0,0],
                [0,0,1,2,1,0,0,0,0,0,0,0,0,0,1,2,1,0,0],
                [0,1,2,2,1,1,1,1,1,1,1,1,1,1,1,2,2,1,0],
                [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
                [0,1,2,2,1,1,1,1,1,1,1,1,1,1,1,2,2,1,0],
                [0,0,1,2,1,0,0,0,0,0,0,0,0,0,1,2,1,0,0],
                [0,0,0,1,1,0,0,0,0,0,0,0,0,0,1,1,0,0,0],
                [0,0,0,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
            ],[#bottomleft/topright arrow
                [0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,2,1],
                [0,0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,1,1],
                [0,0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,1],
                [0,0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0],
                [1,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0],
                [1,1,0,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,2,2,2,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0],
                [1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0]
            ],[#circle w arrows
                [0,0,0,0,0,0,1,1,1,1,1,1,1,0,0,0,0,0,0],
                [0,0,0,0,1,1,2,2,2,2,2,2,2,1,1,0,0,0,0],
                [0,0,0,1,2,2,2,2,2,1,2,2,2,2,2,1,0,0,0],
                [0,0,1,2,2,2,2,2,1,1,1,2,2,2,2,2,1,0,0],
                [0,1,2,2,2,2,2,1,1,1,1,1,2,2,2,2,2,1,0],
                [0,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,0],
                [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
                [1,2,2,2,1,2,2,2,2,2,2,2,2,2,1,2,2,2,1],
                [1,2,2,1,1,2,2,2,2,1,2,2,2,2,1,1,2,2,1],
                [1,2,2,2,2,2,2,2,1,1,1,2,2,2,1,1,1,2,1],
                [1,2,2,1,1,2,2,2,2,1,2,2,2,2,1,1,2,2,1],
                [1,2,2,2,1,2,2,2,2,2,2,2,2,2,1,2,2,2,1],
                [1,2,2,2,2,2,2,2,2,2,2,2,2,2,1,2,2,2,1],
                [0,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,0],
                [0,1,2,2,2,2,2,1,1,1,1,1,2,2,2,2,2,1,0],
                [0,0,1,2,2,2,2,2,1,1,1,2,2,2,2,2,1,0,0],
                [0,0,0,1,2,2,2,2,2,1,2,2,2,2,2,1,0,0,0],
                [0,0,0,0,1,1,2,2,2,2,2,2,2,1,1,0,0,0,0],
                [0,0,0,0,0,0,1,1,1,1,1,1,1,0,0,0,0,0,0]
            ],[#no circle all arrows
                [0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,2,0,1,0,0,0,0,0,0],
                [0,0,0,0,0,1,1,1,1,2,1,1,1,1,0,0,0,0,0],
                [0,0,0,0,1,0,0,0,1,2,1,0,0,0,1,0,0,0,0],
                [0,0,0,1,1,0,0,0,1,2,1,0,0,0,1,1,0,0,0],
                [0,0,1,2,1,0,0,0,1,2,1,0,0,0,1,2,1,0,0],
                [0,1,2,2,1,1,1,1,1,2,1,1,1,1,1,2,2,1,0],
                [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
                [0,1,2,2,1,1,1,1,1,2,1,1,1,1,1,2,2,1,0],
                [0,0,1,2,1,0,0,0,1,2,1,0,0,0,1,2,1,0,0],
                [0,0,0,1,1,0,0,0,1,2,1,0,0,0,1,1,0,0,0],
                [0,0,0,0,1,0,0,0,1,2,1,0,0,0,1,0,0,0,0],
                [0,0,0,0,0,1,1,1,1,2,1,1,1,1,0,0,0,0,0],
                [0,0,0,0,0,0,1,2,2,2,2,2,1,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,1,2,1,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0]
            ]
        ]
        i,t,p = win32gui.GetCursorInfo()
        print(t if trace else "",end="")
        verticalOffset = 0
        horizontalOffset = 0
        ct = 0
        if t == 31918455:#inverted
            ct = 1
        elif t == 65569:#finger
            ct = 2
        elif t == 65543:#bar
            ct = 3
            verticalOffset = -9
            horizontalOffset = -8
        elif t == 65557:#up/down arrow
            ct = 4
            verticalOffset = -9
        elif t == 65551:#topleft/bottomright arrow
            ct = 5
            verticalOffset = -9
            horizontalOffset = -9
        elif t == 65555:#left/right arrow
            ct = 6
            horizontalOffset = -9
        elif t == 65553:#bottomleft/topright arrow
            ct = 7
            verticalOffset = -9
            horizontalOffset = -9
        elif t == 17697265 or t == 259656119:#circle w arrow
            ct = 8
        elif t == 1902623:#no circle all arrows
            ct = 9
        else:#regular
            ct = 0
        
        s=19
       
        for r in range(s):
            for c in range(s):
                try:
                    if x >= 0 and y >= 0:
                        if cursor[ct][r][c] == 1:
                            frame[y+r+verticalOffset][x+c+horizontalOffset] = (0,0,0)
                        elif cursor[ct][r][c] == 2:
                            frame[y+r+verticalOffset][x+c+horizontalOffset] = (255,255,255)
                except Exception:
                    pass
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (self.res), interpolation=cv2.INTER_AREA)
        return frame