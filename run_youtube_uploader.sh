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

# Set environment (respect an explicit ENV override, e.g. ENV=staging)
export ENV="${ENV:-production}"

# Use the in-tree virtual environment (never a venv from another folder)
VENV="$SCRIPT_DIR/venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
    log "ERROR: Virtual environment not found or not executable at $PY"
    exit 1
fi

# Fail loudly if the env profile is missing: load_dotenv() returns False
# silently, leaving every credential as None and producing confusing failures.
if [ ! -f "$SCRIPT_DIR/.env.$ENV" ]; then
    log "ERROR: $SCRIPT_DIR/.env.$ENV not found (ENV=$ENV)"
    exit 1
fi

log "Using interpreter: $PY"
log "Env file: .env.$ENV"

# Run the pipeline (English only; the Chinese pipeline is a separate script)
log "Executing main.py --language en"
"$PY" "$SCRIPT_DIR/main.py" --language en 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

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
