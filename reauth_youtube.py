#!/home/ubuntu/youtube-uploader/venv/bin/python
"""YouTube OAuth reauthorization helper.

Safe defaults: --print-url only prints the Google consent URL. Credentials are
only written when --callback-url and --write are both supplied.

Profiles:
  upload     -> youtube_credentials.pickle (durable videos.insert token)
  force-ssl  -> youtube_force_ssl_credentials.pickle (privacy/status updates)
"""
import argparse
import os
# Localhost callback is intentionally used for out-of-band server reauth, and
# Google may return already-granted OpenID/userinfo scopes alongside YouTube.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
import pickle
import shutil
from datetime import datetime, timezone

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


def profile_config(profile):
    return PROFILES[profile]


def credentials_path(profile):
    return os.path.join(BASE_DIR, profile_config(profile)["credentials_file"])


def make_flow(profile):
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS,
        scopes=profile_config(profile)["scopes"],
        redirect_uri=REDIRECT_URI,
    )


def print_url(profile):
    flow = make_flow(profile)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    print(url)


def write_credentials(profile, callback_url):
    scopes = profile_config(profile)["scopes"]
    path = credentials_path(profile)
    flow = make_flow(profile)
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

    with open(path, "wb") as f:
        pickle.dump(creds, f)
    os.chmod(path, 0o600)

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
