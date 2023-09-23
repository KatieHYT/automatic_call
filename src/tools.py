import queue
import speech_recognition as sr
import audioop
from typing import List, Optional
import os
import tempfile
from gtts import gTTS
import subprocess
import whisper
import io
from pydub import AudioSegment
import time
import openai
import sys
import random

sys.path.append("..")
from src.text_to_speech import ElevenLabTTS
from src.text_to_speech import UnrealSpeechTTS

class QueueStream:
    def __init__(self):
        self.q = queue.Queue(maxsize=-1)

    def read(self, chunk: int) -> bytes:
        return self.q.get()

    def write(self, chunk: bytes):
        self.q.put(chunk)

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

class TalkerCradle:
    """
    Audio (listn to talker_x) -> TalkerCradle -> Audio (file on disk)

    phone_operator: transmit Audio(file on disk) to talker_x via Twilio
    """

    def __init__(
            self,
            static_dir: str,
            whisper_model_size: str = "base.en"
            ):
        
        # STT: Speech to Text
        self.audio_listener = sr.Recognizer()
        print(f"Loading whisper {whisper_model_size}...")
        self.audio2text_sys = whisper.load_model(whisper_model_size)
        print("\tDone.")
        

        self.static_dir = static_dir
        self.phone_operator = None
        
        voice_list = [
                'Rachel',
                'Clyde',
                'Domi',
                'Dave', # good descent man
                'Fin',
                'Bella',
                'Antoni',
                'Thomas',
                'Charlie',
                #'Emily',
                'Elli',
                'Callum',
                'Patrick',
                'Harry',
                'Liam',
                #'Dorothy',
                'Josh',
                'Arnold',
                'Charlotte',
                'Matilda',
                'Matthew',
                'James',
                'Joseph',
                'Jeremy',
                'Michael',
                'Ethan',
                'Gigi',
                'Freya',
                'Grace',
                'Daniel',
                'Serena',
                'Adam',
                'Nicole',
                'Jessie', # good descent man
                'Ryan',
                'Sam',
                'Glinda',
                'Giovanni',
                'Mimi',
                ]
        self.selected_voice = random.choice(voice_list)
        print(f"Seleted Voice: {self.selected_voice}")
        # TTS: Text to Speech
        #self.text2audio_sys = ElevenLabTTS(selected_voice=self.selected_voice) 
        self.text2audio_sys = UnrealSpeechTTS()

        self.thinking_phrase_list = [
                "ok",
                "right",
                "I see",
                "Got it",
                "understood",
                "okay",
                "well",
                "Mhmm",
                "Uh-huh",
                "Hmm",
                #"woooooo...",
                "alright",
                ]
        self.system_prompt=f"Pretend you are a human who has a dog, during the phone call, you are a customer, you need to check detailed dog policy from the store. Ask yes/no question each time."
        self.init_phrase=f"Hello, this is {self.selected_voice}. Can I bring my dog to your place?"
        self.messages = [
                {"role": "system", "content": self.system_prompt},
            ]

        self.bye_txt_list = [
            "ok. I see. Have a great day! Bye bye.",
            "I Got it. Thanks. Bye",
            "Understood. Thank you. Goodbye!",
                ]

    def gpt_get_response(self) -> str:
        output = openai.ChatCompletion.create(
            #model="gpt-3.5-turbo",
            model="gpt-4",
            messages=self.messages,
        )
        response = output["choices"][0]["message"]["content"]

        return response

    def get_audio_fn_and_key(self, text: str):
        key = str(abs(hash(text)))
        path = os.path.join(self.static_dir, key + ".mp3")
        return key, path

    def think_what_to_say(self, init=False, content=None):
        if init:
            self.messages.append({
                "role": "assistant",
                "content": self.init_phrase,
                })
            text = self.init_phrase
            
        else:
            self.messages.append({
                "role": "user",
                "content": content,
                })
            print("\t ChatGPT processing...")
            start_time = time.time()
            text = self.gpt_get_response()
            self.messages.append({
                "role": "assistant",
                "content": text,
                })
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
         
        print("\t Adjusting ambient noise...")
        start_time = time.time()
        self.audio_listener.adjust_for_ambient_noise(source, duration=2)
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")

        print("\t Listening...")
        start_time = time.time()
        audio = self.audio_listener.listen(source, None, 7)
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")

        print("\t Wav to bytes...")
        start_time = time.time()
        data = io.BytesIO(audio.get_wav_data())
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")

        print("\t Audio to disk...")
        start_time = time.time()
        audio_clip = AudioSegment.from_file(data)
        audio_clip.export(tmp_path, format="wav")
        end_time = time.time()
        time_taken = end_time - start_time
        print("\t\t Time taken:", time_taken, "seconds")

        return tmp_path

    def listen_and_transcribe(self, talker_x) -> str:
        # listen what talker_x talking
        with talker_x as source:
            print("Listening to talker_x...")
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = self.record_audio_to_disk(source, tmp_dir)
                
                print("\t Speech to text...")
                start_time = time.time()
                result = self.audio2text_sys.transcribe(tmp_path, language="english", fp16=False)
                end_time = time.time()
                time_taken = end_time - start_time
                print("\t\t Time taken:", time_taken, "seconds")
                predicted_text = result["text"]
                print(f"[Recipient]:\t {predicted_text}")

        return predicted_text

