#!/bin/bash
echo "Starting to trigger gunicorn"
gunicorn --bind  0.0.0.0:5000 "flask_server:create_app()" & 
sleep 5
echo "Starting Nginx Service"
nginx -g 'daemon off;'
