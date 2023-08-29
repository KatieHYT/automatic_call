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
    apt-get install -y apache2 && \
    apt-get install -y ffmpeg

# Copy the Apache configuration file
COPY flask-app.conf /etc/apache2/sites-available/flask-app.conf

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

## Upgrade pip
#RUN python -m pip install --upgrade pip

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Set the working directory in the container
WORKDIR /app/script

# Make port 80 available to the world outside this container
EXPOSE 80

## Run the Flask app
#CMD ["python", "flask_server.py", "--host=0.0.0.0", "--port=80"]

## Enable the virtual host configuration
#RUN ln -s /etc/apache2/sites-available/flask-app.conf /etc/apache2/sites-enabled/
#
## Restart Apache to apply the configuration
#CMD ["apachectl", "-k", "restart"]
