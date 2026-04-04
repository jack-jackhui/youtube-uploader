#!/bin/bash
#
# YouTube Uploader Cron Wrapper
# Handles environment setup, execution, and error reporting
#

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
LOG_FILE="$SCRIPT_DIR/cron.log"
MAX_LOG_SIZE=5000000  # 5MB - rotate if larger
LOCK_FILE="/tmp/youtube_uploader.lock"

# Timestamp function
timestamp() {
    date "+%Y-%m-%d %H:%M:%S UTC"
}

log() {
    echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"
}

# Rotate log if too large
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "${LOG_FILE}.1"
    log "Log rotated"
fi

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log "ERROR: Another instance is running (PID: $LOCK_PID). Exiting."
        exit 1
    else
        log "WARNING: Stale lock file found, removing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "=========================================="
log "Pipeline run starting"
log "=========================================="

# Set environment
export ENV="production"

# Activate virtual environment
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    log "ERROR: Virtual environment not found at $SCRIPT_DIR/venv"
    exit 1
fi

# Run the pipeline
log "Executing main.py --language en"
python "$SCRIPT_DIR/main.py" --language en 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Deactivate venv
deactivate 2>/dev/null

# Report result
if [ $EXIT_CODE -eq 0 ]; then
    log "Pipeline completed successfully"
else
    log "Pipeline failed with exit code: $EXIT_CODE"
fi

log "=========================================="
log "Pipeline run finished (exit code: $EXIT_CODE)"
log "==========================================\n"

exit $EXIT_CODE
