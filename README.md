# automatic_call

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
