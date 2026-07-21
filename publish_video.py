#!/usr/bin/env python3
"""
Publish a previously uploaded private YouTube video.

Usage:
    python publish_video.py <video_id>
    python publish_video.py <video_id> --unlisted  # Make unlisted instead of public
"""

import sys
import argparse
from youtube_manager import authenticate_youtube, update_video_privacy


def main():
    parser = argparse.ArgumentParser(description="Publish a private YouTube video")
    parser.add_argument("video_id", help="YouTube video ID to publish")
    parser.add_argument("--unlisted", action="store_true", 
                       help="Make unlisted instead of public")
    args = parser.parse_args()
    
    privacy = "unlisted" if args.unlisted else "public"
    
    print(f"Publishing video {args.video_id} as {privacy}...")
    
    try:
        youtube = authenticate_youtube(require_force_ssl=True)
        update_video_privacy(youtube, args.video_id, privacy)
        print(f"Video {args.video_id} is now {privacy.upper()}")
        print(f"  URL: https://youtube.com/watch?v={args.video_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
