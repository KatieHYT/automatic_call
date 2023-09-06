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
                'Dave',
                'Fin',
                'Bella',
                'Antoni',
                'Thomas',
                'Charlie',
                'Emily',
                'Elli',
                'Callum',
                'Patrick',
                'Harry',
                'Liam',
                'Dorothy',
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
                'Jessie',
                'Ryan',
                'Sam',
                'Glinda',
                'Giovanni',
                'Mimi',
                ]
        self.selected_voice = random.choice(voice_list)
        print(f"Seleted Voice: {self.selected_voice}")
        # TTS: Text to Speech
        self.text2audio_sys = ElevenLabTTS(selected_voice=self.selected_voice) 

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
                "alright",
                ]
        self.system_prompt=f"You are the one who has a dog, you need to check detailed dog policy of the store you are going to. In each exchange, ask the recipient only one yes/no question."
        self.init_phrase=f"Hello, this is {self.selected_voice}. Can I bring my dog to your place?"

    def get_response(self, transcript: List[str]) -> str:
        if len(transcript) > 0:
            messages = [
                {"role": "system", "content": self.system_prompt},
            ]
            for i, text in enumerate(reversed(transcript)):
                messages.insert(1, {"role": "user" if i % 2 == 0 else "assistant", "content": text})
            output = openai.ChatCompletion.create(
                #model="gpt-3.5-turbo",
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

