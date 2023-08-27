from abc import ABC, abstractmethod
import subprocess
from gtts import gTTS
import os
import requests


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
    def __init__(self):
        self.ELEVEN_LABS_API_KEY = os.environ["ELEVEN_LABS_API_KEY"]
        self.ELEVEN_LABS_VOICE_ID = os.environ["ELEVEN_LABS_VOICE_ID"]

    def text_to_mp3(self, text: str, output_fn: str) -> str:
        url = f'https://api.elevenlabs.io/v1/text-to-speech/{self.ELEVEN_LABS_VOICE_ID}'
        headers = {
            'accept': 'audio/mpeg',
            'xi-api-key': self.ELEVEN_LABS_API_KEY,
            'Content-Type': 'application/json'
        }
        data = {
            'text': text,
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.25
            }
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            with open(output_fn, "wb") as out:
                # Write the response to the output file.
                out.write(response.content)
        else:
            assert 1==0, "fix it!"

