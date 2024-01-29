## The server client is the one that will be recieving the video stream from the host
import Streamer as stream
import threading

reciever = stream.StreamerClient('10.0.0.88',1234)

t = threading.Thread(target=reciever.startClient)
t.start()

while input("") != 'exit':
    continue

reciever.stopClient()