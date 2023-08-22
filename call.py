
from gevent import monkey

monkey.patch_all()


import logging
import time
import os
import openai
from abc import ABC, abstractmethod
from typing import List, Optional
import io
import tempfile
import queue
import functools
from pydub import AudioSegment
import speech_recognition as sr
import whisper
import threading
import logging
import os
import base64
import json
import time

from gevent.pywsgi import WSGIServer
from twilio.rest import Client
from flask import Flask, send_from_directory
from flask_sock import Sock
import simple_websocket
import audioop

XML_MEDIA_STREAM = """
<Response>
    <Start>
        <Stream name="Audio Stream" url="wss://{host}/audiostream" />
    </Start>
    <Pause length="60"/>
</Response>
"""

#XML_TEST = """
#<Response>
#    <Say>Thanks for calling! I'm Yu-Ting Huang</Say>
#    <Pause length="5"/>
#</Response>
#"""
openai.api_key = os.environ["OPENAI_KEY"]

class OpenAIChatCompletion:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def get_response(self, transcript: List[str]) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        for i, text in enumerate(reversed(transcript)):
            messages.insert(1, {"role": "user" if i % 2 == 0 else "assistant", "content": text})
        output = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return output["choices"][0]["message"]["content"]

class ChatAgent(ABC):
    @abstractmethod
    def get_response(self, transcript: List[str]) -> str:
        pass

    def start(self):
        pass

class OpenAIChat(ChatAgent):
    def __init__(self, system_prompt: str, init_phrase: Optional[str] = None):
        self.openai_chat = OpenAIChatCompletion(system_prompt=system_prompt)
        self.init_phrase = init_phrase

    def get_response(self, transcript: List[str]) -> str:
        if len(transcript) > 0:
            response = self.openai_chat.get_response(transcript)
        else:
            response = self.init_phrase
        return response

def run_conversation(agent_a: ChatAgent, agent_b: ChatAgent):
    transcript = []
    while True:
        text_a = agent_a.get_response(transcript)
        transcript.append(text_a)
        print("->", text_a, transcript)
        text_b = agent_b.get_response(transcript)
        transcript.append(text_b)
        print("->", text_b, transcript)

@functools.cache
def get_whisper_model(size: str = "large"):
    logging.info(f"Loading whisper {size}")
    return whisper.load_model(size)


class WhisperMicrophone:
    def __init__(self):
        self.audio_model = get_whisper_model()
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 500
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_threshold = False

    def get_transcription(self) -> str:
        with sr.Microphone(sample_rate=16000) as source:
            logging.info("Waiting for mic...")
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = os.path.join(tmp, "mic.wav")
                audio = self.recognizer.listen(source)
                data = io.BytesIO(audio.get_wav_data())
                audio_clip = AudioSegment.from_file(data)
                audio_clip.export(tmp_path, format="wav")
                result = self.audio_model.transcribe(tmp_path, language="english")
            predicted_text = result["text"]
        return predicted_text

class _TwilioSource(sr.AudioSource):
    def __init__(self, stream):
        self.stream = stream
        self.CHUNK = 1024
        self.SAMPLE_RATE = 8000
        self.SAMPLE_WIDTH = 2

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

class _QueueStream:
    def __init__(self):
        self.q = queue.Queue(maxsize=-1)

    def read(self, chunk: int) -> bytes:
        return self.q.get()

    def write(self, chunk: bytes):
        self.q.put(chunk)


class WhisperTwilioStream:
    def __init__(self):
        self.audio_model = get_whisper_model()
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 2.5
        self.recognizer.dynamic_energy_threshold = False
        self.stream = None

    def get_transcription(self) -> str:
        self.stream = _QueueStream()
        with _TwilioSource(self.stream) as source:
            logging.info("Waiting for twilio caller...")
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = os.path.join(tmp, "mic.wav")
                audio = self.recognizer.listen(source)
                data = io.BytesIO(audio.get_wav_data())
                audio_clip = AudioSegment.from_file(data)
                audio_clip.export(tmp_path, format="wav")
                result = self.audio_model.transcribe(tmp_path, language="english")
        predicted_text = result["text"]
        self.stream = None
        return predicted_text

class TwilioServer:
    def __init__(self, remote_host: str, port: int, static_dir: str):
        self.app = Flask(__name__)
        self.sock = Sock(self.app)
        self.remote_host = remote_host
        self.port = port
        self.static_dir = static_dir
        self.server_thread = threading.Thread(target=self._start)
        self.on_session = None

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        self.from_phone = os.environ["TWILIO_PHONE_NUMBER"]
        self.client = Client(account_sid, auth_token)

        @self.app.route("/audio/<key>")
        def audio(key):
            return send_from_directory(self.static_dir, str(int(key)) + ".mp3")

        @self.app.route("/incoming-voice", methods=["POST"])
        def incoming_voice():
            return XML_MEDIA_STREAM.format(host=self.remote_host)

        @self.sock.route("/audiostream", websocket=True)
        def on_media_stream(ws):
            session = TwilioCallSession(ws, self.client, remote_host=self.remote_host, static_dir=self.static_dir)
            if self.on_session is not None:
                thread = threading.Thread(target=self.on_session, args=(session,))
                thread.start()
            session.start_session()

    def start_call(self, to_phone: str):
        self.client.calls.create(
            twiml=XML_MEDIA_STREAM.format(host=self.remote_host),
            to=to_phone,
            from_=self.from_phone,
        )

    def _start(self):
        logging.info("Starting Twilio Server")
        WSGIServer(("0.0.0.0", self.port), self.app).serve_forever()

    def start(self):
        self.server_thread.start()


class TwilioCallSession:
    def __init__(self, ws, client: Client, remote_host: str, static_dir: str):
        self.ws = ws
        self.client = client
        self.sst_stream = WhisperTwilioStream()
        self.remote_host = remote_host
        self.static_dir = static_dir
        self._call = None

    def media_stream_connected(self):
        return self._call is not None

    def _read_ws(self):
        while True:
            try:
                message = self.ws.receive()
            except simple_websocket.ws.ConnectionClosed:
                logging.warn("Call media stream connection lost.")
                break
            if message is None:
                logging.warn("Call media stream closed.")
                break

            data = json.loads(message)
            if data["event"] == "start":
                logging.info("Call connected, " + str(data["start"]))
                self._call = self.client.calls(data["start"]["callSid"])
            elif data["event"] == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if self.sst_stream.stream is not None:
                    self.sst_stream.stream.write(audioop.ulaw2lin(chunk, 2))
            elif data["event"] == "stop":
                logging.info("Call media stream ended.")
                break

    def get_audio_fn_and_key(self, text: str):
        key = str(abs(hash(text)))
        path = os.path.join(self.static_dir, key + ".mp3")
        return key, path

    def play(self, audio_key: str, duration: float):
        self._call.update(
            twiml=f'<Response><Play>https://{self.remote_host}/audio/{audio_key}</Play><Pause length="60"/></Response>'
        )
        time.sleep(duration + 0.2)

    def start_session(self):
        self._read_ws()

logging.getLogger().setLevel(logging.INFO)

tws = TwilioServer(remote_host="https://2394-140-112-41-151.ngrok-free.app", port=2000, static_dir=r"./")
# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice
tws.start()


agent_a = OpenAIChat(
        system_prompt="You are a Haiku Assistant. Answer whatever the user wants but always in a rhyming Haiku.",
        init_phrase="This is Haiku Bot, how can I help you.",
 )


#agent_a = OpenAIChat(
#    system_prompt="""
#You are an ordering bot that is going to call a pizza place an order a pizza.
#When you need to say numbers space them out (e.g. 1 2 3) and do not respond with abbreviations.
#If they ask for information not known, make something up that's reasonable.
#
#The customer's details are:
#* Address: 1234 Candyland Road, Apt 506
#* Credit Card: 1234 5555 8888 9999 (CVV: 010)
#* Name: Bob Joe
#* Order: 1 large pizza with only pepperoni
#""",
#    init_phrase="Hi, I would like to order a pizza.",
#)

def run_chat(sess):
    agent_b = TwilioCaller(sess)
    while not agent_b.session.media_stream_connected():
        time.sleep(0.1)
    run_conversation(agent_a, agent_b)
    
tws.on_session = run_chat


# You can also have ChatGPT actually start the call, e.g. for automated ordering
tws.start_call("+14156054429")
