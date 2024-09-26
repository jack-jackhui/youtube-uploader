#!/bin/bash

# Change directory to the location of this script
cd "$(dirname "$0")"

# Set the environment variable
export ENV="production"  # Change to "dev" for development environment

# Activate the virtual environment
source /home/ubuntu/youtube-uploader/venv/bin/activate

# Run your Python script to generate and upload English video
python /home/ubuntu/youtube-uploader/main.py --language en

# Run your Python script to generate and upload Chinese video
python /home/ubuntu/youtube-uploader/main.py --language zh

# Deactivate the virtual environment
deactivate
