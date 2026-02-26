#!/bin/bash
set -e

# Change to script directory
cd "$(dirname "$0")"

# Set environment
export ENV="production"

# Activate venv
source venv/bin/activate

# Log start
echo "[$(date)] Starting Chinese video generation..."

# Run the script
python main.py --language zh

# Log completion
echo "[$(date)] Completed."

deactivate
