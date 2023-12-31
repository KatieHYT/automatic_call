# automatic_call
This is the repo for `automatic call` on our website [**Cradle.wiki**](http://cradle.wiki/).  

For `review summary`, go check repo: https://github.com/KatieHYT/pet_friendly  

For backend and frontend, please refer to: https://github.com/KatieHYT/cradle-django & https://github.com/KatieHYT/cradle-vite

`Together, make the world better! ^__^ ` 

## Environment setting & Usage
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
  cd automatic_call
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
- open another terminal(remember to enter the container)
  ```
  cd automatic_call
  ```
- create your `.env` file to store environemnt variables
  ```
  export TWILIO_ACCOUNT_SID="..."
  export TWILIO_AUTH_TOKEN="..."
  export TWILIO_PHONE_NUMBER="..."
  export REMOTE_HOST_URL="<ngrok url from the above step>"
  export OPENAI_API_KEY="..."
  
  export ELEVEN_LABS_API_KEY="..."
  export ELEVEN_LABS_VOICE_ID="..."
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
  cd automatic_call
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
