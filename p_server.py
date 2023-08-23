
from gevent.pywsgi import WSGIServer
from flask import Flask, render_template
from flask_sockets import Sockets


app = Flask(__name__)
sock = Sockets(app)
@app.route("/twiml", methods=["POST"])
def incoming_voice():
    print("????????????????")
    return render_template("streams.xml")

@sock.route("/")
def on_media_stream(ws):
    print("!!!!")

# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

server = pywsgi.WSGIServer(
    ("", 2000), app, handler_class=WebSocketHandler
)
print("Server listening on: http://localhost:" + str(2000))
server.serve_forever()
