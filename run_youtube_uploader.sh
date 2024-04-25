#!/bin/bash

# Set the environment variable
export ENV="production"  # Change to "dev" for development environment

# Activate the virtual environment
source /home/ubuntu/youtube-uploader/venv/bin/activate

# Run your Python script
python /home/ubuntu/youtube-uploader/main.py

# Deactivate the virtual environment
deactivate
