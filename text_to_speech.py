from typing import List, Optional
import os
import tempfile
from gtts import gTTS
import subprocess

class GoogleTTS:
    def text_to_mp3(self, text: str, output_fn: Optional[str] = None) -> str:
        tmp_fn = output_fn or os.path.join(tempfile.mkdtemp(), "tts.mp3")
        tts = gTTS(text, lang="en")
        tts.save(tmp_fn)
        return tmp_fn

    def get_duration(self, audio_fn: str) -> float:
        popen = subprocess.Popen(
            ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries", "format=duration", "-i", audio_fn],
            stdout=subprocess.PIPE,
        )
        popen.wait()
        output = popen.stdout.read().decode("utf-8")
        duration = float(output.split("=")[1].split("\n")[0])
        return duration

