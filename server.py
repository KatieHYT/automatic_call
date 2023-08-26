from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import openai
from pydub import AudioSegment
import io
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
from flask import Flask, render_template, send_from_directory
from flask_sockets import Sockets
import speech_recognition as sr
import whisper
import functools
import threading
import time
from gtts import gTTS
import subprocess

openai.api_key = os.environ["OPENAI_KEY"]

XML_MEDIA_STREAM = """
<Response>
  <Start>
    <Stream url="wss://{host}/"></Stream>
  </Start>
  <Pause length="60"/>
  <Say>
	  Hello KT
  </Say>
</Response>
"""

class GoogleTTS:
    def text_to_mp3(self, text: str, output_fn: Optional[str] = None) -> str:
        tmp_fn = output_fn or os.path.join(tempfile.mkdtemp(), "tts.mp3")
        tts = gTTS(text, lang="en")
        tts.save(tmp_fn)
        return tmp_fn

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
        duration = float(output.split("=")[1].split("\n")[0])
        return duration

class TalkerCradle:
    def __init__(
            self,
            system_prompt: str,
            static_dir: str,
            remote_host: str,
            init_phrase: Optional[str] = None,
            thinking_phrase: str = "OK",
            whisper_model_size: str = "tiny"
            ):
        
        self.system_prompt = system_prompt
        self.init_phrase = init_phrase
        self.thinking_phrase = thinking_phrase

        # STT: Speech to Text
        self.audio_listener = sr.Recognizer()
        #self.audio_listener.energy_threshold = 300
        #self.audio_listener.pause_threshold = 2.5
        #self.audio_listener.dynamic_energy_threshold = False
        print(f"Loading whisper {whisper_model_size}...")
        self.audio2text_sys = whisper.load_model(whisper_model_size)
        print("Done.")
        
        # TTS: Text to Speech
        self.text2audio_sys = GoogleTTS() 

        self.static_dir = static_dir
        self.remote_host = remote_host

        self._call = None
        self.talker_x_stream = None

    def get_response(self, transcript: List[str]) -> str:
        if len(transcript) > 0:
            messages = [
                {"role": "system", "content": self.system_prompt},
            ]
            for i, text in enumerate(reversed(transcript)):
                messages.insert(1, {"role": "user" if i % 2 == 0 else "assistant", "content": text})
            output = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
            )
            response = output["choices"][0]["message"]["content"]
        else:
            response = self.init_phrase
        return response

    def get_audio_fn_and_key(self, text: str):
        key = str(abs(hash(text)))
        path = os.path.join(self.static_dir, key + ".mp3")
        return key, path

    def say(self, transcript):
        text = self.get_response(transcript)
        print(f"[Cradle]:\t {text}")

        self.play_text_audio(text)

        return text

    def play_text_audio(self, text: str):
        audio_key, tts_fn = self.get_audio_fn_and_key(text)
        self.text2audio_sys.text_to_mp3(text, output_fn=tts_fn)
        duration = self.text2audio_sys.get_duration(tts_fn)
        self._call.update(
            twiml=f'<Response><Play>https://{self.remote_host}/audio/{audio_key}</Play><Pause length="60"/></Response>'
        )
        time.sleep(duration + 0.2)

    def record_audio_to_disk(self, source, tmp_dir):
        tmp_path = os.path.join(tmp_dir, "mic.wav")
        # wait for thinking at most 4 seconds
        # wait for the response at most 5 secons
        audio = self.audio_listener.listen(source)
        data = io.BytesIO(audio.get_wav_data())
        audio_clip = AudioSegment.from_file(data)
        audio_clip.export(tmp_path, format="wav")

        return tmp_path

    def listen_and_transcribe(self, talker_x) -> str:
        talker_x.stream = _QueueStream()
        with talker_x as source:
            print("Waiting for twilio caller...")
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = self.record_audio_to_disk(source, tmp_dir)
                result = self.audio2text_sys.transcribe(tmp_path, language="english", fp16=False)

        predicted_text = result["text"]
        print(f"[Recipient]:\t {predicted_text}")
        self.play_text_audio(self.thinking_phrase)

        talker_x.stream = None

        return predicted_text

class TalkerX(sr.AudioSource):
    def __init__(self, stream):
        self.stream = stream 
        self.CHUNK = 1024 # number of frames stored in each buffer
        self.SAMPLE_RATE = 8000 # sampling rate in Hertz
        self.SAMPLE_WIDTH = 2 

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def write_audio_data_to_stream(self, chunk):
        # μ-law encoded audio data to linear encoding, and then writes the converted data to the audio stream.
        tmp = audioop.ulaw2lin(chunk, 2)
        self.stream.write(tmp)

class _QueueStream:
    def __init__(self):
        self.q = queue.Queue(maxsize=-1)

    def read(self, chunk: int) -> bytes:
        return self.q.get()

    def write(self, chunk: bytes):
        self.q.put(chunk)

class CradleCallCenter:
    def __init__(self, remote_host: str, port: int, static_dir: str):
        self.app = Flask(__name__)
        self.sock = Sockets(self.app)
        self.remote_host = remote_host
        self.port = port
        self.static_dir = static_dir

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        self.from_phone = os.environ["TWILIO_PHONE_NUMBER"]
        self.twilio_client = Client(account_sid, auth_token)
        
        self.agent_a = TalkerCradle(
                system_prompt="You are conducting a dog-friendly survey. In each exchange, ask only one yes/no question.",
                init_phrase="Hello, this is Cradle.wiki. Can I bring my dog to your place?",
                remote_host=self.remote_host,
                static_dir=self.static_dir,
         )

        @self.app.route("/twiml", methods=["POST"])
        def incoming_voice():
            print("---> inside /twiml")
            return XML_MEDIA_STREAM.format(host=self.remote_host)
        
        @self.sock.route("/")
        def on_media_stream(ws):
            print("---> inside /    socket")
            self.talker_x = TalkerX(stream = None)
            thread = threading.Thread(target=self.on_session, args=())
            thread.start()
            self._read_ws(ws)

        @self.app.route("/audio/<key>")
        def audio(key):
            return send_from_directory(self.static_dir, str(int(key)) + ".mp3")

    def _read_ws(self, ws):
        while True:
            try:
                message = ws.receive()
            except simple_websocket.ws.ConnectionClosed:
                logging.warn("Call media stream connection lost.")
                break
            if message is None:
                logging.warn("Call media stream closed.")
                break
            data = json.loads(message)
            if data["event"] == "start":
                print("Call connected, " + str(data["start"]))
                self.agent_a._call = self.twilio_client.calls(data["start"]["callSid"])
            elif data["event"] == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if self.talker_x.stream is not None:
                    self.talker_x.write_audio_data_to_stream(chunk)
                    
            elif data["event"] == "stop":
                print("Call media stream ended.")
                break

    def on_session(self,):
        while not (self.agent_a._call is not None):
            time.sleep(0.1)

        transcript_list = []
        while True:
            text_a = self.agent_a.say(transcript_list)
            transcript_list.append(text_a)

            text_b = self.agent_a.listen_and_transcribe(self.talker_x)
            transcript_list.append(text_b)
            
    def start(self,):
        server = pywsgi.WSGIServer(
            ("", self.port), self.app, handler_class=WebSocketHandler
        )
        print("Server listening on: http://localhost:" + str(self.port))
        server.serve_forever()

if __name__ == '__main__':
    # force to use CPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    
    tws = CradleCallCenter(remote_host=os.environ["REMOTE_HOST_URL"], port=2000, static_dir='./any_audio')
    tws.start()
    
