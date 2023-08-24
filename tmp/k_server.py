from pydub import AudioSegment
import os
import tempfile
import openai
import io
import base64
import json
import threading

from flask import Flask, render_template
from flask_sockets import Sockets
from google.cloud.speech import RecognitionConfig, StreamingRecognitionConfig

from SpeechClientBridge import SpeechClientBridge

HTTP_SERVER_PORT = 2000

config = RecognitionConfig(
    encoding=RecognitionConfig.AudioEncoding.MULAW,
    sample_rate_hertz=8000,
    language_code="en-US",
)
streaming_config = StreamingRecognitionConfig(config=config, interim_results=True)

app = Flask(__name__)
sockets = Sockets(app)


@app.route("/twiml", methods=["POST"])
def return_twiml():
    print("POST TwiML")
    return render_template("streams.xml")


def on_transcription_response(response):
    binary_data = response
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = os.path.join(tmp, "mic.wav")
        data = io.BytesIO(binary_data)
        audio_clip = AudioSegment.from_file(data)
        audio_clip.export(tmp_path, format="wav")
        result = self.audio_model.transcribe(tmp_path, language="english")
    
    print(result)


@sockets.route("/")
def transcript(ws):
    print("WS connection opened")
    bridge = SpeechClientBridge(streaming_config, on_transcription_response)
    t = threading.Thread(target=bridge.start)
    t.start()

    while not ws.closed:
        message = ws.receive()
        if message is None:
            bridge.add_request(None)
            bridge.terminate()
            break

        data = json.loads(message)
        if data["event"] in ("connected", "start"):
            print(f"Media WS: Received event '{data['event']}': {message}")
            continue
        if data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            bridge.add_request(chunk)
        if data["event"] == "stop":
            print(f"Media WS: Received event 'stop': {message}")
            print("Stopping...")
            break

    bridge.terminate()
    print("WS connection closed")


if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(
        ("", HTTP_SERVER_PORT), app, handler_class=WebSocketHandler
    )
    print("Server listening on: http://localhost:" + str(HTTP_SERVER_PORT))
    server.serve_forever()
