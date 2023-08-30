# automatic_call

## Environment setting
- install docker
  ```
  sudo apt-get update
  sudo apt  install docker.io
  ```
- get your free authtoken from `https://ngrok.com/`
- run docker container
  it takes some time to download the image   
  ```
  docker run -d -e NGROK_AUTHTOKEN=<your ngrok authtoken> -it --name cradle_call -p 2000:2000 -v /:/TOP nvcr.io/nvidia/pytorch:23.07-py3
  ```
- enter into the container
  ```
  docker exec -it cradle_call bash
  ```
- git clone this repo
- install packages
  ```
  pip install -r requirements.txt
  pip install git+https://github.com/openai/whisper.git
  apt-get update
  apt-get install -y ffmpeg
  ```
- install ngrok
  ```
  curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null &&
              echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | tee /etc/apt/sources.list.d/ngrok.list &&
              apt update && apt install ngrok   
  ```
- open another terminal (remember to enter the container) to start ngrok service (assume you port forward on 2000)
  ```
  ngrok http 2000
  ```
- copy ngrok url
  ```
  https://<copy this part!!!> -> http://localhost:2000

  e.g., 
  https://aba4-54-190-224-84.ngrok-free.app -> http://localhost:2000

  then you copy: aba4-54-190-224-84.ngrok-free.app
  ```
- create your `.env` file to store environemnt variables
  ```
  export TWILIO_ACCOUNT_SID="AC3af075b86d82096251b059536575eb8c"
  export TWILIO_AUTH_TOKEN="e547a2b0504b9e868db89084b47507ea"
  export TWILIO_PHONE_NUMBER="+18777495792"
  export REMOTE_HOST_URL="<ngrok url from the above step>"
  export OPENAI_API_KEY="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"
  
  export ELEVEN_LABS_API_KEY="8770d56af60ac360f8b25f453a95cbd3"
  export ELEVEN_LABS_VOICE_ID="LcfcDJNUP1GQjkzn1xUU"
  ```
- export environment variables
  ```
  source .env
  ```
- start flask app
  ```
  cd script
  python flask_server.py
  ```
- open another terminal (remember to enter the container) export `.env`again
  ```
  source .env
  cd script
  ```
- make a call
  ```
  python call.py
  ```

## deploy on AWS
- Step-1: install docker
  ```
  sudo apt-get update
  sudo apt  install docker.io
  ```
- Step-2: build docker image
  ```
  docker build -t flask_docker .
  ```

- Step-3: run docker container
  ```
  docker run -d --env-file .env -p 80:80 --name flask_container flask_docker
  ```
