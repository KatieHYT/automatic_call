import os
import requests
from elevenlabs import generate
from elevenlabs import set_api_key
import time

txt = "Can I bring my dog to your place?"
N_RUN = 10

#print("elevenlab")
#set_api_key(os.environ["ELEVEN_LABS_API_KEY"])

print("unreal speech")
UNREAL_SPEECH_API_KEY = os.environ["UNREAL_SPEECH_API_KEY"]


time_list = []
for i in range(N_RUN):
    start_time = time.time()


    #audio = generate(
    #    text=txt,
    #    voice="Emily",
    #    model='eleven_monolingual_v1'
    #)


    response = requests.post(
      'https://api.v6.unrealspeech.com/stream',
      headers = {
        'Authorization' : UNREAL_SPEECH_API_KEY
      },
      json = {
        'Text': f'''{txt}''', # Up to 500 characters
        'VoiceId': 'Scarlett', # Dan, Will, Scarlett, Liv, Amy
        'Bitrate': '192k', # 320k, 256k, 192k, ...
        'Speed': '0', # -1.0 to 1.0
        'Pitch': '0.99', # -0.5 to 1.5
        'Codec': 'libmp3lame', # libmp3lame or pcm_mulaw
      }
    )



    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"{i}--> {elapsed_time}")
    time_list.append(elapsed_time)







total_sum = sum(time_list)

# Calculate the average
average = total_sum / N_RUN
print(f"average in {N_RUN}: {average}")
