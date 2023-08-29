# Use an official Python runtime as a parent image
FROM nvcr.io/nvidia/pytorch:23.07-py3

# Set the environment variable to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory in the container
WORKDIR /app/

# Copy the current directory contents into the container at /app
COPY . /app

# Install Apache2 and other required packages
RUN apt-get update && \
    apt-get install -y tzdata && \
    apt-get install -y nginx && \
    apt-get install -y ffmpeg

# Copy the Apache configuration file
COPY nginx_config.conf /etc/nginx/conf.d/virtual.conf

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set the working directory in the container
WORKDIR /app/script

# Make port 80 available to the world outside this container
EXPOSE 80

RUN chmod +x ./start.sh
ENTRYPOINT ["./start.sh"]
