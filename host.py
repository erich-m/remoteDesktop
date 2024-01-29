## The server host is the one that will be sending the video stream to the client
import Streamer as stream
import threading

sender = stream.HostStreamer('10.0.0.88',1234)

t = threading.Thread(target=sender.serverStart)
t.start()

while input("") != 'exit':
    continue

sender.serverStop()