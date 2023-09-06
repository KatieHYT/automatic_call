from abc import ABC, abstractmethod
import subprocess
from gtts import gTTS
import os
import requests
from elevenlabs import generate
from elevenlabs import set_api_key

class TTSHelper(ABC):
    @abstractmethod
    def text_to_mp3(self, text: str, output_fn: str) -> str:
        pass

    def get_duration(self, audio_fn: str) -> float:
        popen = subprocess.Popen(
            ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries", "format=duration", "-i", audio_fn],
            stdout=subprocess.PIPE,
        )
        popen.wait()
        output = popen.stdout.read().decode("utf-8")
        duration = float(output.split("=")[1].split("\n")[0])

        return duration

class GoogleTTS(TTSHelper):
    def text_to_mp3(self, text: str, output_fn: str) -> str:
        tts = gTTS(text, lang="en")
        tts.save(output_fn)

class ElevenLabTTS(TTSHelper):
    def __init__(self, selected_voice):
        set_api_key(os.environ["ELEVEN_LABS_API_KEY"])
        self.selected_voice = selected_voice

    def text_to_mp3(self, text: str, output_fn: str) -> str:
        audio = generate(
            text=text,
            voice=self.selected_voice,
            model='eleven_monolingual_v1'
        )
        with open(output_fn, "wb") as out:
            out.write(audio)
