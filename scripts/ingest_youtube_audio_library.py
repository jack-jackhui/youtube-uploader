#!/usr/bin/env python3
"""Ingest downloaded YouTube Audio Library MP3s into ai-video-api approved BGM."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/music/approved/manifest.json"
STAGED = ROOT / "assets/music/approved"
DEFAULT_MAX_BYTES = 900_000  # public nginx currently rejects >~1MB uploads


def slugify(name: str) -> str:
    name = Path(name).stem.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return name[:80] or "track"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_env(env: str) -> None:
    env_file = ROOT / f".env.{env}"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def transcode_for_upload(src: Path, track_id: str, max_bytes: int) -> Path:
    STAGED.mkdir(parents=True, exist_ok=True)
    dst = STAGED / f"{track_id}.mp3"
    if src.stat().st_size <= max_bytes:
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        return dst

    # Use a 30s seed; ai-video-api loops BGM to the video duration during render.
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-t", "30",
        "-af", "afade=t=in:st=0:d=1.5,afade=t=out:st=28:d=2,loudnorm=I=-23:LRA=7:TP=-2",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg transcode failed")
    if dst.stat().st_size > max_bytes:
        raise RuntimeError(f"transcoded file still too large: {dst.stat().st_size} bytes")
    return dst


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"tracks": []}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + chr(10))


def upload(api_host: str, api_key: str, path: Path) -> str:
    url = api_host.rstrip("/") + "/api/v1/musics"
    with path.open("rb") as f:
        resp = requests.post(
            url,
            headers={"X-API-Key": api_key},
            files={"file": (path.name, f, "audio/mpeg")},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["file"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="Downloaded YouTube Audio Library MP3 files")
    ap.add_argument("--mood", action="append", default=[], help="Mood/tag to add; repeatable")
    ap.add_argument("--source-note", default="YouTube Audio Library", help="Source/licence note")
    ap.add_argument("--license", default="YouTube Audio Library", help="Licence label")
    ap.add_argument("--max-upload-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = ap.parse_args()

    env = os.getenv("ENV", "production")
    load_env(env)
    api_host = os.getenv("API_HOST")
    api_key = os.getenv("API_KEY")
    if not api_host or not api_key:
        raise SystemExit("Missing API_HOST/API_KEY from .env.production")

    manifest = load_manifest()
    by_id = {t.get("id"): t for t in manifest.get("tracks", [])}

    for raw in args.files:
        src = Path(raw).expanduser().resolve()
        if not src.exists() or src.suffix.lower() != ".mp3":
            print(f"skip non-mp3/missing: {src}", file=sys.stderr)
            continue
        track_id = slugify(src.name)
        staged = transcode_for_upload(src, track_id, args.max_upload_bytes)
        remote_file = upload(api_host, api_key, staged)
        item = {
            "id": track_id,
            "file": remote_file,
            "local_file": str(staged.relative_to(ROOT)),
            "sha256": sha256(staged),
            "source": args.source_note,
            "license": args.license,
            "mood": args.mood,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "original_filename": src.name,
        }
        by_id[track_id] = item
        print(f"uploaded {src.name} -> {remote_file}")

    manifest["tracks"] = sorted(by_id.values(), key=lambda x: x.get("id", ""))
    save_manifest(manifest)
    print(f"updated {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
