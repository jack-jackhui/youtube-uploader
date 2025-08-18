#!/bin/bash

# Clear Chromium cache directories
#rm -rf "/c/Users/YourUsername/AppData/Local/Chromium/User Data/Default/Cache/*"
#rm -rf "/c/Users/YourUsername/AppData/Local/Chromium/User Data/Default/*"

# Change directory to the location of this script
cd "$(dirname "$0")"

# Set the environment variable
export ENV="production"  # Change to "dev" for development environment

# Activate the virtual environment
source "/c/Users/jack/Python-Apps/youtube-uploader/venv/bin/activate"

# Run your Python script to generate and upload English video
# python "/c/Users/YourUsername/youtube-uploader/main.py" --language en

# Run your Python script to generate and upload Chinese video
python "/c/Users/jack/Python-Apps/youtube-uploader/main.py" --language zh

# Run test script
# python "/c/Users/YourUsername/youtube-uploader/test/test_up.py"

# Deactivate the virtual environment
deactivate