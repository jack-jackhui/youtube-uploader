"""
Safe background music generation for YouTube uploads.

This avoids Content ID risk from random third-party BGM by generating a
low-volume procedural ambient bed locally and mixing it under the narration.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


DEFAULT_BGM_VOLUME = float(os.getenv("SAFE_BGM_VOLUME", "0.055"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _probe_duration(video_path: str) -> float:
    result = _run([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return max(float(result.stdout.strip()), 0.1)


def add_safe_background_music(video_path: str, volume: float | None = None) -> str:
    """
    Add self-generated ambient BGM under an existing narrated video.

    Returns the processed output path. If SAFE_BGM_ENABLED=false, returns the
    original video path unchanged.
    """
    if os.getenv("SAFE_BGM_ENABLED", "true").lower() == "false":
        print("[SafeBGM] Disabled (SAFE_BGM_ENABLED=false)")
        return video_path

    input_path = Path(video_path)
    if not input_path.exists():
        raise FileNotFoundError(video_path)

    duration = _probe_duration(str(input_path))
    fade_out_start = max(duration - 2.0, 0.0)
    bgm_volume = DEFAULT_BGM_VOLUME if volume is None else float(volume)
    output_path = input_path.with_name(f"{input_path.stem}_safe_bgm{input_path.suffix}")

    # Layer three quiet sine tones into a soft ambient chord. This is generated
    # from scratch, not sampled from any music library, so it avoids third-party
    # Content ID claims from bundled/random tracks.
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-f", "lavfi", "-t", f"{duration:.3f}", "-i", "sine=frequency=196:sample_rate=44100",
        "-f", "lavfi", "-t", f"{duration:.3f}", "-i", "sine=frequency=246.94:sample_rate=44100",
        "-f", "lavfi", "-t", f"{duration:.3f}", "-i", "sine=frequency=329.63:sample_rate=44100",
        "-filter_complex",
        (
            "[1:a]volume=0.50[a1];"
            "[2:a]volume=0.35[a2];"
            "[3:a]volume=0.25[a3];"
            "[a1][a2][a3]amix=inputs=3:duration=longest,"
            "lowpass=f=900,afade=t=in:st=0:d=2,"
            f"afade=t=out:st={fade_out_start:.3f}:d=2,"
            f"volume={bgm_volume}[bed];"
            "[0:a]volume=1.0[voice];"
            "[voice][bed]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        ),
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]

    print(f"[SafeBGM] Adding self-generated background music: volume={bgm_volume}, duration={duration:.1f}s")
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg SafeBGM mix failed")
    print(f"[SafeBGM] Output: {output_path}")
    return str(output_path)
