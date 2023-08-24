from typing import List, Optional
from abc import ABC, abstractmethod
import tempfile
import audioop
import queue
import json
import base64
import os
from twilio.rest import Client
from gevent.pywsgi import WSGIServer
from flask import Flask, render_template
from flask_sockets import Sockets
import speech_recognition as sr
import whisper
import functools
import threading
import time
from gtts import gTTS
import subprocess

class TTSClient(ABC):
    @abstractmethod
    def text_to_mp3(self, text: str, output_fn: Optional[str] = None) -> str:
        pass

    def play_text(self, text: str) -> str:
        tmp_mp3 = self.text_to_mp3(text)
        tmp_wav = tmp_mp3.replace(".mp3", ".wav")
        subprocess.call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp_mp3, tmp_wav])

        wf = wave.open(tmp_wav, "rb")
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=audio.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )

        data = wf.readframes(1024)
        while data != b"":
            stream.write(data)
            data = wf.readframes(1024)

        stream.close()
        audio.terminate()

    def get_duration(self, audio_fn: str) -> float:
        popen = subprocess.Popen(
            ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries", "format=duration", "-i", audio_fn],
            stdout=subprocess.PIPE,
        )
        popen.wait()
        output = popen.stdout.read().decode("utf-8")
        print("==================================", output)
        duration = float(output.split("=")[1].split("\r")[0])
        return duration

class GoogleTTS(TTSClient):
    def text_to_mp3(self, text: str, output_fn: Optional[str] = None) -> str:
        tmp_fn = output_fn or os.path.join(tempfile.mkdtemp(), "tts.mp3")
        tts = gTTS(text, lang="en")
        tts.save(tmp_fn)
        return tmp_fn


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

def run_conversation(agent_a: ChatAgent, agent_b: ChatAgent):
    transcript = []
    while True:
        text_a = agent_a.get_response(transcript)
        transcript.append(text_a)
        print("->", text_a, transcript)
        text_b = agent_b.get_response(transcript)
        transcript.append(text_b)
        print("->", text_b, transcript)

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

class TTSClient(ABC):
    @abstractmethod
    def text_to_mp3(self, text: str, output_fn: Optional[str] = None) -> str:
        pass

    def play_text(self, text: str) -> str:
        tmp_mp3 = self.text_to_mp3(text)
        tmp_wav = tmp_mp3.replace(".mp3", ".wav")
        subprocess.call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp_mp3, tmp_wav])

        wf = wave.open(tmp_wav, "rb")
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=audio.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )

        data = wf.readframes(1024)
        while data != b"":
            stream.write(data)
            data = wf.readframes(1024)

        stream.close()
        audio.terminate()

    def get_duration(self, audio_fn: str) -> float:
        popen = subprocess.Popen(
            ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries", "format=duration", "-i", audio_fn],
            stdout=subprocess.PIPE,
        )
        popen.wait()
        output = popen.stdout.read().decode("utf-8")
        duration = float(output.split("=")[1].split("\r")[0])
        return duration

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
                print("Call connected, " + str(data["start"]))
                self._call = self.client.calls(data["start"]["callSid"])
            elif data["event"] == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if self.sst_stream.stream is not None:
                    tmp = audioop.ulaw2lin(chunk, 2)
                    self.sst_stream.stream.write(tmp)
                    text = self.sst_stream.get_transcription()
                    
                    print(text)
            elif data["event"] == "stop":
                print("Call media stream ended.")
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


class TwilioCaller(ChatAgent):
    def __init__(self, session: TwilioCallSession, tts: Optional[TTSClient] = None, thinking_phrase: str = "OK"):
        self.session = session
        self.speaker = tts or GoogleTTS()
        self.thinking_phrase = thinking_phrase

    def _say(self, text: str):
        key, tts_fn = self.session.get_audio_fn_and_key(text)
        self.speaker.text_to_mp3(text, output_fn=tts_fn)
        duration = self.speaker.get_duration(tts_fn)
        self.session.play(key, duration)

    def get_response(self, transcript: List[str]) -> str:
        if len(transcript) > 0:
            self._say(transcript[-1])
        resp = self.session.sst_stream.get_transcription()
        self._say(self.thinking_phrase)
        return resp

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


@functools.cache
def get_whisper_model(size: str = "large"):
    print(f"Loading whisper {size}...")
    _m = whisper.load_model(size)
    print("Done.")
    return _m


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
            print("Waiting for twilio caller...")
            with tempfile.TemporaryDirectory() as tmp:
                print("come inside????")
                tmp_path = os.path.join(tmp, "mic.wav")
                print(tmp_path)
                audio = self.recognizer.listen(source)
                print('audio')
                data = io.BytesIO(audio.get_wav_data())
                print('data')
                audio_clip = AudioSegment.from_file(data)
                print('clip')
                audio_clip.export(tmp_path, format="wav")
                print('export')
                result = self.audio_model.transcribe(tmp_path, language="english")
                print("done transcribe")
                print(result)
        predicted_text = result["text"]
        self.stream = None
        return predicted_text

class TwilioServer:
    def __init__(self, remote_host: str, port: int, static_dir: str):
        self.app = Flask(__name__)
        self.sock = Sockets(self.app)
        self.remote_host = remote_host
        self.port = port
        self.static_dir = static_dir

        self.on_session = None
        
        if self.on_session is None:
            print("I'm None")
        else:
            print("I got it.")

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        self.from_phone = os.environ["TWILIO_PHONE_NUMBER"]
        self.client = Client(account_sid, auth_token)

        @self.app.route("/twiml", methods=["POST"])
        def incoming_voice():
            print("????????????????")
            return render_template("streams.xml")
        
        @self.sock.route("/")
        def on_media_stream(ws):
            print("!!!!")
            session = TwilioCallSession(ws, self.client, remote_host=self.remote_host, static_dir=self.static_dir)
            if self.on_session is not None:
                thread = threading.Thread(target=self.on_session, args=(session,))
                thread.start()
            session.start_session()

    def start(self,):
        server = pywsgi.WSGIServer(
            ("", self.port), self.app, handler_class=WebSocketHandler
        )
        print("Server listening on: http://localhost:" + str(self.port))
        server.serve_forever()

# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

tws = TwilioServer(remote_host="2394-140-112-41-151.ngrok-free.app", port=2000, static_dir='./')


agent_a = OpenAIChat(
        system_prompt="You are a Haiku Assistant. Answer whatever the user wants but always in a rhyming Haiku.",
        init_phrase="This is Haiku Bot, how can I help you.",
 )
def run_chat(sess):
    agent_b = TwilioCaller(sess)
    while not agent_b.session.media_stream_connected():
        time.sleep(0.1)
    run_conversation(agent_a, agent_b)
print("pre put")
tws.on_session = run_chat
print("after put")


tws.start()





# Point twilio voice webhook to https://abcdef.ngrok.app/audio/incoming-voice