#!/bin/bash
#
# WinningCV Campaign Publisher
# Generates and publishes the next WinningCV backlog video to YouTube Shorts and Instagram Reels.
# XHS remains disabled for this English-language campaign.
#

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/winningcv.log"
MAX_LOG_SIZE=5000000
LOCK_FILE="/tmp/winningcv_uploader.lock"
BACKLOG_FILE="${WINNINGCV_BACKLOG_FILE:-$SCRIPT_DIR/winning-cv-video-backlog.json}"
STATE_FILE="$SCRIPT_DIR/winningcv_state.json"

timestamp() {
    date -u "+%Y-%m-%d %H:%M:%S UTC"
}

log() {
    echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"
}

if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "${LOG_FILE}.1"
    log "Log rotated"
fi

if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log "ERROR: Another WinningCV uploader instance is running (PID: $LOCK_PID). Exiting."
        exit 1
    fi
    log "WARNING: Stale lock file found, removing"
    rm -f "$LOCK_FILE"
fi

echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

if [ ! -f "$BACKLOG_FILE" ]; then
    log "ERROR: Backlog file not found: $BACKLOG_FILE"
    log "Set WINNINGCV_BACKLOG_FILE to the private campaign backlog path, or create $SCRIPT_DIR/winning-cv-video-backlog.json from the example."
    exit 1
fi

CAMPAIGN_DAY=$(BACKLOG_FILE="$BACKLOG_FILE" STATE_FILE="$STATE_FILE" "$SCRIPT_DIR/venv/bin/python" - <<"PY"
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

backlog_file = os.environ["BACKLOG_FILE"]
state_file = os.environ["STATE_FILE"]
with open(backlog_file, encoding="utf-8") as f:
    data = json.load(f)
videos = data.get("videos", data if isinstance(data, list) else [])
if not videos:
    print("ERROR:no videos", file=sys.stderr)
    sys.exit(2)

if os.path.exists(state_file):
    try:
        with open(state_file, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("day"):
            print(int(state["day"]))
            sys.exit(0)
    except Exception:
        pass

start = data.get("start_date") or videos[0].get("publish_date")
if not start:
    print(1)
    sys.exit(0)
start_date = datetime.strptime(start, "%Y-%m-%d").date()
today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
day = (today - start_date).days + 1
if day < 1:
    day = 1
max_day = max(int(v.get("day", i + 1)) for i, v in enumerate(videos))
if day > max_day:
    print(f"COMPLETE:{day}:{max_day}")
else:
    print(day)
PY
)

if [[ "$CAMPAIGN_DAY" == COMPLETE:* ]]; then
    log "WinningCV campaign complete ($CAMPAIGN_DAY). Nothing to publish."
    exit 0
fi

if ! [[ "$CAMPAIGN_DAY" =~ ^[0-9]+$ ]]; then
    log "ERROR: Could not compute campaign day: $CAMPAIGN_DAY"
    exit 1
fi

log "=========================================="
log "WinningCV campaign run starting (day $CAMPAIGN_DAY)"
log "=========================================="

export ENV="production"
export SKIP_YT_UPLOAD="false"
export SKIP_IG_UPLOAD="false"
export XHS_MCP_ENABLED="false"

if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    log "ERROR: Virtual environment not found at $SCRIPT_DIR/venv"
    exit 1
fi

log "Executing main.py --language en --campaign winningcv --backlog $BACKLOG_FILE --day $CAMPAIGN_DAY"
python "$SCRIPT_DIR/main.py" --language en --campaign winningcv --backlog "$BACKLOG_FILE" --day "$CAMPAIGN_DAY" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

deactivate 2>/dev/null

if [ $EXIT_CODE -eq 0 ]; then
    log "WinningCV pipeline completed successfully"
else
    log "WinningCV pipeline failed with exit code: $EXIT_CODE"
fi

log "=========================================="
log "WinningCV campaign run finished (exit code: $EXIT_CODE)"
log "=========================================="

exit $EXIT_CODE
