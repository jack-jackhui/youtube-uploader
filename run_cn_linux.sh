#!/bin/bash
# run_cn_linux.sh - Chinese video generation pipeline (cron entrypoint)
#
# Consolidated 2026-11-15: this tree (/home/jack/youtube-uploader, lowercase)
# is now canonical. Previously cron ran the stale capital-Y symlink into
# /mnt/seagate, which had older code, no git history, and a hollowed-out venv.
#
# - Uses /home/jack/YouTube-uploader-venv (on native disk, not the NTFS mount)
# - Fails loudly: a missing interpreter or env file aborts instead of
#   silently running with every credential set to None.
#
set -uo pipefail

cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

VENV="/home/jack/YouTube-uploader-venv"
PY="$VENV/bin/python"

export ENV="${ENV:-production}"

if [ ! -x "$PY" ]; then
    echo "[$(date)] FATAL: venv python not found at $PY"
    exit 127
fi

# Fail loudly if the env file for this ENV is missing. load_dotenv() returns
# False silently in that case, leaving every API key as None.
if [ ! -f "$SCRIPT_DIR/.env.$ENV" ]; then
    echo "[$(date)] FATAL: .env.$ENV not found in $SCRIPT_DIR (ENV=$ENV)"
    exit 78
fi

echo "[$(date)] Starting Chinese video generation..."
echo "[$(date)] Tree: $SCRIPT_DIR"
echo "[$(date)] Env file: .env.$ENV"
echo "[$(date)] Using interpreter: $PY"

"$PY" main.py --language zh
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo "[$(date)] Completed successfully."
    exit 0
fi

echo "[$(date)] FAILED with exit status $STATUS"

# Email alert on failure. Never let notifying itself mask the exit code.
"$PY" - "$STATUS" <<'PYEOF'
import os, sys, traceback
status = sys.argv[1]
try:
    sys.path.insert(0, os.getcwd())
    from dotenv import load_dotenv
    env = os.getenv("ENV", "production")
    load_dotenv(dotenv_path=f".env.{env}")
    load_dotenv(dotenv_path=".env")
    from email_notifier import send_email
    recipient = os.getenv("NOTIFICATION_EMAIL") or os.getenv("EMAIL_USER")
    body = (
        f"The Chinese video generation cron job FAILED.\n\n"
        f"Host: {os.uname().nodename}\n"
        f"Time: {__import__('datetime').datetime.now().isoformat()}\n"
        f"Tree: {os.getcwd()}\n"
        f"Env file: .env.{env}\n"
        f"Exit status: {status}\n"
        f"Interpreter: /home/jack/YouTube-uploader-venv/bin/python\n"
        f"Log: /home/jack/youtube-uploader/cron.log\n\n"
        f"Last 40 log lines are attached below.\n"
    )
    try:
        with open("cron.log", "r", errors="replace") as f:
            body += "\n" + "".join(f.readlines()[-40:])
    except Exception:
        body += "\n(could not read cron.log)\n"
    if recipient:
        send_email("[YouTube Uploader] Cron FAILED (exit %s)" % status, body, [recipient])
        print("Failure alert emailed to %s" % recipient)
    else:
        print("No NOTIFICATION_EMAIL/EMAIL_USER configured; alert not sent")
except Exception:
    print("Could not send failure alert:")
    traceback.print_exc()
PYEOF

exit "$STATUS"
