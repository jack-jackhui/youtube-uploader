#!/home/ubuntu/youtube-uploader/venv/bin/python
"""YouTube OAuth reauthorization helper.

Safe defaults: --print-url only prints the Google consent URL. Credentials are
only written when --callback-url and --write are both supplied.

Profiles:
  upload     -> youtube_credentials.pickle (durable videos.insert token)
  force-ssl  -> youtube_force_ssl_credentials.pickle (privacy/status updates)

PKCE RESUMPTION
---------------
Google embeds a PKCE code_challenge in the consent URL. The matching
code_verifier only lives inside the Flow object that produced that URL, so a
second process can never redeem the code. To make the documented two-step flow
work, --print-url persists the pending flow (state + code_verifier) to a 0600
file, and --callback-url reloads it and rebuilds a Flow carrying the same
verifier. Codes expire in ~10 minutes; stale pending state is discarded.
"""
import argparse
import json
import os
import stat
import sys
import time
# Localhost callback is intentionally used for out-of-band server reauth, and
# Google may return already-granted OpenID/userinfo scopes alongside YouTube.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
import pickle
import shutil
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

PROFILES = {
    "upload": {
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
        "credentials_file": "youtube_credentials.pickle",
    },
    "force-ssl": {
        "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
        "credentials_file": "youtube_force_ssl_credentials.pickle",
    },
}
REDIRECT_URI = "http://127.0.0.1:9090/accounts/google/login/callback/"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS = os.path.join(BASE_DIR, "client_secrets.json")
# Authorization codes are short-lived (~10 min); 15 min covers clock skew.
PENDING_MAX_AGE_SECONDS = 15 * 60


def profile_config(profile):
    return PROFILES[profile]


def credentials_path(profile):
    return os.path.join(BASE_DIR, profile_config(profile)["credentials_file"])


def pending_path(profile):
    return os.path.join(BASE_DIR, f".oauth_pending_{profile}.json")


def make_flow(profile):
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS,
        scopes=profile_config(profile)["scopes"],
        redirect_uri=REDIRECT_URI,
    )


def _write_private(path, data, mode=0o600):
    """Write bytes with owner-only permissions (created atomically)."""
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def save_pending(profile, flow):
    """Persist the PKCE verifier + state so a later invocation can redeem the code."""
    pending = {
        "profile": profile,
        "state": flow.oauth2session._state,
        "code_verifier": flow.code_verifier,
        "redirect_uri": REDIRECT_URI,
        "created_at": int(time.time()),
    }
    blob = json.dumps(pending).encode()
    _write_private(pending_path(profile), blob)
    return pending_path(profile)


def load_pending(profile):
    """Load saved PKCE state, discarding it if missing, malformed, or stale."""
    path = pending_path(profile)
    if not os.path.exists(path):
        raise SystemExit(
            f"No pending authorization for profile '{profile}'. "
            f"Run --print-url first, then redeem within 10 minutes."
        )
    try:
        pending = json.loads(open(path, "r").read())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Pending authorization unreadable ({exc}). Re-run --print-url.")

    age = int(time.time()) - int(pending.get("created_at", 0))
    if age > PENDING_MAX_AGE_SECONDS:
        os.unlink(path)
        raise SystemExit(
            f"Pending authorization for '{profile}' is {age}s old and the code has "
            f"expired. Re-run --print-url and redeem promptly."
        )
    if pending.get("profile") != profile:
        raise SystemExit(
            f"Pending authorization belongs to profile '{pending.get('profile')}', "
            f"not '{profile}'. Re-run --print-url."
        )
    if not pending.get("code_verifier"):
        raise SystemExit("Pending authorization has no code_verifier. Re-run --print-url.")
    return pending


def clear_pending(profile):
    path = pending_path(profile)
    if os.path.exists(path):
        os.unlink(path)


def print_url(profile):
    clear_pending(profile)
    flow = make_flow(profile)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    path = save_pending(profile, flow)
    print(url)
    print(
        f"\n# PKCE state saved to {path} (valid 10 min).\n"
        f"# Redeem with: --profile {profile} --callback-url 'URL' --write",
        file=sys.stderr,
    )
    return url


def _state_from_callback(callback_url):
    """Fail fast with a clear message when the pasted URL carries no code/state."""
    try:
        qs = parse_qs(urlparse(callback_url).query)
    except ValueError:
        return None, None
    code = (qs.get("code") or [None])[0]
    state = (qs.get("state") or [None])[0]
    if qs.get("error"):
        raise SystemExit(f"Google returned an error: {(qs.get('error') or ['unknown'])[0]}")
    return code, state


def write_credentials(profile, callback_url):
    scopes = profile_config(profile)["scopes"]
    path = credentials_path(profile)
    pending = load_pending(profile)

    code, state = _state_from_callback(callback_url)
    if code and set(code) == {"…"} or (code and "\u2026" in code):
        raise SystemExit(
            "The pasted code looks truncated (contains an ellipsis '…'). "
            "Copy the FULL callback URL from the address bar."
        )
    if not code:
        raise SystemExit("Callback URL has no code= parameter. Paste the full redirected URL.")
    if state and pending.get("state") and state != pending["state"]:
        raise SystemExit(
            "State mismatch: this callback came from an older --print-url run. "
            "Re-run --print-url and redeem the newest link."
        )

    # Rebuild a Flow that carries the verifier saved by --print-url.
    flow = make_flow(profile)
    flow.code_verifier = pending["code_verifier"]
    if pending.get("state"):
        flow.oauth2session._state = pending["state"]

    flow.fetch_token(authorization_response=callback_url)
    creds = flow.credentials
    if not creds.has_scopes(scopes):
        raise SystemExit(f"Granted scopes insufficient: {creds.granted_scopes or creds.scopes}")

    if os.path.exists(path):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = f"{path}.bak.{stamp}"
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
        print(f"Backed up existing credentials to {backup}")

    _write_private(path, pickle.dumps(creds))
    clear_pending(profile)

    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if items:
        ch = items[0]
        print(f"Verified channel: {ch['snippet'].get('title')} / {ch.get('id')}")
    print(f"Saved {profile} credentials to {path}")


def main():
    parser = argparse.ArgumentParser(description="Reauthorize YouTube OAuth credentials")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="force-ssl", help="Credential profile to create/update")
    parser.add_argument("--print-url", action="store_true", help="Print Google OAuth consent URL")
    parser.add_argument("--callback-url", help="Full redirected callback URL containing code=...")
    parser.add_argument("--write", action="store_true", help="Actually save credentials after exchanging callback URL")
    args = parser.parse_args()

    if args.print_url:
        print_url(args.profile)
        return 0
    if args.callback_url:
        if not args.write:
            raise SystemExit("Refusing to write credentials without --write")
        write_credentials(args.profile, args.callback_url)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
