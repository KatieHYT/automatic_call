from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import openai
from pydub import AudioSegment
import io
from typing import List, Optional
from abc import ABC, abstractmethod
import audioop
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
import tempfile

from text_to_speech import GoogleTTS
from tools import QueueStream

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

class TalkerCradle:
    def __init__(
            self,
            system_prompt: str,
            static_dir: str,
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

    def think_what_to_say(self, transcript):
        print("\t ChatGPT processing...")
        start_time = time.time()
        text = self.get_response(transcript)
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")
        print(f"[Cradle]:\t {text}")

        print("\t Text to audio...")
        start_time = time.time()
        audio_key, duration = self.text_to_audiofile(text)
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")

        return text, audio_key, duration

    def text_to_audiofile(self, text: str):
        audio_key, tts_fn = self.get_audio_fn_and_key(text)
        self.text2audio_sys.text_to_mp3(text, output_fn=tts_fn)
        duration = self.text2audio_sys.get_duration(tts_fn)
        
        return audio_key, duration

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
        # listen what talker_x talking
        with talker_x as source:
            print("Listening to talker_x...")
            with tempfile.TemporaryDirectory() as tmp_dir:
                print("\t Audio to disk...")
                start_time = time.time()
                tmp_path = self.record_audio_to_disk(source, tmp_dir)
                end_time = time.time()
                time_taken = end_time - start_time
                print("\t\t Time taken:", time_taken, "seconds")

                
                print("\t Speech to text...")
                start_time = time.time()
                result = self.audio2text_sys.transcribe(tmp_path, language="english", fp16=False)
                end_time = time.time()
                time_taken = end_time - start_time
                print("\t\t Time taken:", time_taken, "seconds")
                predicted_text = result["text"]
                print(f"[Recipient]:\t {predicted_text}")

        return predicted_text

class TalkerX(sr.AudioSource):
    def __init__(self, ):
        self.stream = None
        self.CHUNK = 1024 # number of frames stored in each buffer
        self.SAMPLE_RATE = 8000 # sampling rate in Hertz
        self.SAMPLE_WIDTH = 2 

    def __enter__(self):
        self.stream = QueueStream()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream = None

    def write_audio_data_to_stream(self, chunk):
        # μ-law encoded audio data to linear encoding, and then writes the converted data to the audio stream.
        tmp = audioop.ulaw2lin(chunk, 2)
        self.stream.write(tmp)

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
                static_dir=self.static_dir,

         )
        
        self._call = None

        @self.app.route("/twiml", methods=["POST"])
        def incoming_voice():
            print("---> inside /twiml")
            return XML_MEDIA_STREAM.format(host=self.remote_host)
        
        @self.sock.route("/")
        def on_media_stream(ws):
            print("---> inside /    socket")
            self.talker_x = TalkerX()
            thread = threading.Thread(target=self.on_session, args=())
            thread.start()
            self._read_ws(ws)

        @self.app.route("/audio/<key>")
        def audio(key):
            return send_from_directory(self.static_dir, str(int(key)) + ".mp3")

    def reply(self, audio_key, duration):
        self._call.update(
            twiml=f'<Response><Play>https://{self.remote_host}/audio/{audio_key}</Play><Pause length="60"/></Response>'
        )
        time.sleep(duration + 0.2)

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
                self._call = self.twilio_client.calls(data["start"]["callSid"])

            elif data["event"] == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if self.talker_x.stream is not None:
                    self.talker_x.write_audio_data_to_stream(chunk)
                    
            elif data["event"] == "stop":
                print("Call media stream ended.")
                break

    def on_session(self,):
        while self._call is None:
            time.sleep(0.1)

        transcript_list = []
        while True:
            text_a, audio_key, duration = self.agent_a.think_what_to_say(transcript_list)
            self.reply(audio_key, duration)
            transcript_list.append(text_a)

            text_b = self.agent_a.listen_and_transcribe(self.talker_x)
            transcript_list.append(text_b)
          
            audio_key, duration = self.agent_a.text_to_audiofile(self.agent_a.thinking_phrase)
            self.reply(audio_key, duration)

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
    
