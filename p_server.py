from gevent.pywsgi import WSGIServer
from flask import Flask, render_template
from flask_sockets import Sockets

class TwilioServer:
    def __init__(self, remote_host: str, port: int):
        self.app = Flask(__name__)
        self.sock = Sockets(self.app)

        @self.app.route("/twiml", methods=["POST"])
        def incoming_voice():
            print("????????????????")
            return render_template("streams.xml")
        
        @self.sock.route("/")
        def on_media_stream(ws):
            print("!!!!")

    def start(self,):
        server = pywsgi.WSGIServer(
            ("", 2000), self.app, handler_class=WebSocketHandler
        )
        print("Server listening on: http://localhost:" + str(2000))
        server.serve_forever()

# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

tws = TwilioServer(remote_host="2394-140-112-41-151.ngrok-free.app", port=2000)
tws.start()
# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice
