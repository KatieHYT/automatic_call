from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import openai
from typing import List, Optional
from abc import ABC, abstractmethod
import json
import base64
import os
from twilio.rest import Client
from gevent.pywsgi import WSGIServer
from flask import Flask, render_template, send_from_directory
from flask_sockets import Sockets
import functools
import threading
import time
import tempfile
import speech_recognition as sr
import sys

sys.path.append("..")
from src.tools import TalkerX, TalkerCradle

class FlaskCallCenter:
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


        @self.app.route("/twiml", methods=["POST"])
        def incoming_voice():
            print("---> inside /twiml")
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
            return XML_MEDIA_STREAM.format(host=self.remote_host)
        
        @self.sock.route("/")
        def on_media_stream(ws):
            print("---> inside /    socket")
            agent_a = TalkerCradle(
                    system_prompt="You are conducting a dog-friendly survey. In each exchange, ask only one yes/no question.",
                    init_phrase="Hello, this is Cradle wiki. Can I bring my dog to your place?",
                    static_dir=self.static_dir,
             )
            talker_x = TalkerX()

            thread = threading.Thread(target=self.conversation, args=(agent_a, talker_x))
            thread.start()

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
                    agent_a.phone_operator = self.twilio_client.calls(data["start"]["callSid"])

                elif data["event"] == "media":
                    media = data["media"]
                    chunk = base64.b64decode(media["payload"])
                    if talker_x.stream is not None:
                        talker_x.write_audio_data_to_stream(chunk)
                        
                elif data["event"] == "stop":
                    print("Call media stream ended.")
                    break

        @self.app.route("/audio/<key>")
        def audio(key):
            return send_from_directory(self.static_dir, str(int(key)) + ".mp3")

    def reply(self, phone_operator, audio_key, duration):
        phone_operator.update(
            twiml=f'<Response><Play>https://{self.remote_host}/audio/{audio_key}</Play><Pause length="60"/></Response>'
        )
        time.sleep(duration + 0.2)

    def hang_up(self, phone_operator):
        phone_operator.update(
            twiml=f'<Response><Hangup/></Response>'
        )

    def conversation(self, agent_a, talker_x):
        while agent_a.phone_operator is None:
            time.sleep(0.1)

        transcript_list = []
        round_cnt = 0
        while round_cnt <=3:
            round_cnt += 1
            text_a, audio_key, duration = agent_a.think_what_to_say(transcript_list)
            self.reply(agent_a.phone_operator, audio_key, duration)
            transcript_list.append(text_a)

            text_b = agent_a.listen_and_transcribe(talker_x)
            transcript_list.append(text_b)
          
            audio_key, duration = agent_a.text_to_audiofile(agent_a.thinking_phrase)
            self.reply(agent_a.phone_operator, audio_key, duration)

        audio_key, duration = agent_a.text_to_audiofile("I got it! Thank you! Good Bye!")
        self.reply(agent_a.phone_operator, audio_key, duration)
        self.hang_up(agent_a.phone_operator)

    def start(self,):
        server = pywsgi.WSGIServer(
            ("", self.port), self.app, handler_class=WebSocketHandler
        )
        print("Server listening on: http://localhost:" + str(self.port))
        server.serve_forever()

    def run(self,):
        return self.app

def create_app():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    openai.api_key = os.environ["OPENAI_API_KEY"]
    static_dir = "./static_dir"
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    
    tws = FlaskCallCenter(remote_host=os.environ["REMOTE_HOST_URL"], port=5000, static_dir=static_dir)

    return tws.run()

if __name__ == '__main__':
    # force to use CPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    openai.api_key = os.environ["OPENAI_API_KEY"]
    static_dir = "./static_dir"
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    
    tws = FlaskCallCenter(remote_host=os.environ["REMOTE_HOST_URL"], port=2000, static_dir=static_dir)
    tws.start()
    
