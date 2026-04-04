# main.py
"""
AI Video Pipeline - Generates and uploads videos to YouTube, Instagram, and Chinese platforms.
"""

import asyncio
import argparse
import sys
import video_api_call
from youtube_manager import authenticate_youtube, upload_video
from voice_manager import get_last_used_voice, get_random_voice, store_last_used_voice
from video_manager import generate_video_subject, process_video_subject, generate_video_and_get_urls
from dotenv import load_dotenv
import os
from smb_path_helper import get_download_path, linux_to_windows_path
from email_notifier import send_email
from instagram_publisher import publish_video_to_instagram
from main_cn import main as chinese_uploader_main
from error_reporter import report_error, report_success, create_run_summary

# Determine which .env file to load
env = os.getenv("ENV", "development")
dotenv_path = f".env.{env}"
load_dotenv(dotenv_path=dotenv_path)

# Environment variables
api_host = os.getenv("API_HOST")
api_key = os.getenv("API_KEY")
openai_api_key = os.getenv("OPEN_AI_KEY")
ig_user_id = os.getenv("IG_USER_ID")
ig_access_token = os.getenv("IG_ACCESS_TOKEN")

print(f"[main.py] Starting up (env={env})")


def main():
    parser = argparse.ArgumentParser(description="Generate and upload videos to various platforms.")
    parser.add_argument("--language", choices=["en", "zh"], default="en", 
                       help="Language of the video")
    args = parser.parse_args()
    language = args.language
    
    # Track results for summary
    results = {
        "Video Generation": {"success": False},
        "YouTube Upload": {"success": False, "skipped": False},
        "Instagram Upload": {"success": False, "skipped": False}
    }
    
    video_subject = None
    
    try:
        # Step 1: Generate video subject
        print(f"\n[Pipeline] Step 1: Generating video subject (language={language})")
        last_voice = get_last_used_voice(language)
        voice_name = get_random_voice(last_voice, language)
        store_last_used_voice(voice_name)
        
        video_subject = generate_video_subject(openai_api_key, language)
        if not video_subject:
            raise Exception("Failed to generate video subject - no topic returned")
        
        print(f"[Pipeline] Video subject: {video_subject}")
        
        # Step 2: Process subject and generate video
        print(f"\n[Pipeline] Step 2: Processing subject and generating video")
        video_script, video_terms, tags = process_video_subject(video_subject, language)
        video_urls = generate_video_and_get_urls(video_subject, video_script, video_terms, voice_name, language)
        
        if not video_urls:
            raise Exception("Failed to generate video - no URLs returned")
        
        original_video_url, converted_video_url = video_urls
        results["Video Generation"] = {
            "success": True,
            "details": f"Generated: {video_subject[:50]}..."
        }
        report_success("Video Generation", {"subject": video_subject, "url": original_video_url})
        
        # Step 3: Platform uploads
        if language == "en":
            # YouTube Upload
            skip_yt = os.getenv("SKIP_YT_UPLOAD", "false").lower() == "true"
            if skip_yt:
                results["YouTube Upload"]["skipped"] = True
                print("[Pipeline] YouTube upload skipped (SKIP_YT_UPLOAD=true)")
            else:
                print(f"\n[Pipeline] Step 3a: Uploading to YouTube")
                try:
                    print(f"[YouTube] Downloading video: {original_video_url}")
                    original_video_path = video_api_call.download_video(
                        original_video_url, video_subject, save_path="downloaded_videos"
                    )
                    
                    if not original_video_path:
                        raise Exception("Failed to download video for YouTube")
                    
                    youtube = authenticate_youtube()
                    upload_response = upload_video(youtube, original_video_path, video_subject, video_subject, tags)
                    
                    if upload_response:
                        video_id = upload_response["id"]
                        results["YouTube Upload"] = {
                            "success": True,
                            "details": f"Video ID: {video_id}"
                        }
                        send_notification_email(video_id)
                        report_success("YouTube Upload", {"video_id": video_id})
                    else:
                        raise Exception("Upload returned no response")
                        
                except Exception as e:
                    results["YouTube Upload"]["error"] = str(e)
                    report_error("YouTube Upload", e, {"video_subject": video_subject})
            
            # Instagram Upload
            skip_ig = os.getenv("SKIP_IG_UPLOAD", "false").lower() == "true"
            if skip_ig:
                results["Instagram Upload"]["skipped"] = True
                print("[Pipeline] Instagram upload skipped (SKIP_IG_UPLOAD=true)")
            else:
                print(f"\n[Pipeline] Step 3b: Uploading to Instagram")
                try:
                    upload_url = converted_video_url if converted_video_url else original_video_url
                    print(f"[Instagram] Using video URL: {upload_url}")
                    
                    success, result = publish_video_to_instagram(ig_user_id, upload_url, ig_access_token)
                    
                    if success:
                        results["Instagram Upload"] = {
                            "success": True,
                            "details": f"Media ID: {result.get('media_id')}"
                        }
                        send_instagram_notification_email()
                        report_success("Instagram Upload", result)
                    else:
                        error_msg = result.get("error", "Unknown error")
                        is_token_error = result.get("is_token_error", False)
                        
                        results["Instagram Upload"]["error"] = error_msg
                        results["Instagram Upload"]["is_token_error"] = is_token_error
                        
                        # Report with specific context for token errors
                        report_error(
                            "Instagram Upload", 
                            Exception(error_msg),
                            {
                                "video_subject": video_subject,
                                "video_url": upload_url,
                                "is_token_error": is_token_error
                            }
                        )
                        
                except Exception as e:
                    results["Instagram Upload"]["error"] = str(e)
                    report_error("Instagram Upload", e, {"video_subject": video_subject})
                    
        elif language == "zh":
            # Chinese platforms
            print(f"\n[Pipeline] Step 3: Uploading to Chinese platforms")
            try:
                video_download_path = get_download_path()
                original_video_path = video_api_call.download_video(
                    original_video_url, video_subject, save_path=video_download_path
                )
                
                if not original_video_path:
                    raise Exception("Failed to download video for Chinese platforms")
                
                original_video_path = linux_to_windows_path(os.path.abspath(original_video_path))
                print(f"[Chinese] Video path: {original_video_path}")
                
                asyncio.run(upload_to_chinese_platforms(
                    original_video_path, video_subject, video_subject, tags, results
                ))
                
            except Exception as e:
                results["Chinese Platforms"] = {"success": False, "error": str(e)}
                report_error("Chinese Platforms", e, {"video_subject": video_subject})
        
    except Exception as e:
        results["Video Generation"]["error"] = str(e)
        report_error("Video Generation", e, {"video_subject": video_subject})
    
    # Print summary
    summary = create_run_summary(results)
    print(summary)
    
    # Determine exit code
    critical_failures = [
        r for r in results.values() 
        if not r.get("success") and not r.get("skipped") and r.get("error")
    ]
    
    if critical_failures:
        print(f"\n[Pipeline] Completed with {len(critical_failures)} failure(s)")
        return 1
    
    print("\n[Pipeline] Completed successfully")
    return 0


async def upload_to_chinese_platforms(video_path, video_subject, video_script, tags, results):
    """Upload video to Chinese platforms."""
    platforms = ["xhs"]
    
    for platform in platforms:
        platform_key = f"Chinese/{platform.upper()}"
        results[platform_key] = {"success": False}
        
        try:
            headless = os.getenv("HEADLESS", "true").lower() == "true"
            use_mcp = platform == "xhs" and os.getenv("XHS_MCP_ENABLED", "false").lower() == "true"
            
            upload_success = await chinese_uploader_main(
                platform_name=platform,
                video_url="",
                video_path=video_path,
                video_name=video_subject,
                cover_path=None,
                description=video_script,
                topics=tags,
                headless=headless,
                use_mcp=use_mcp
            )
            
            if upload_success:
                results[platform_key] = {"success": True, "details": "Upload completed"}
                send_chinese_platform_notification_email(platform, video_subject)
                report_success(f"Chinese/{platform}", {"video": video_subject})
            else:
                raise Exception(f"Upload to {platform} returned failure")
                
        except Exception as e:
            results[platform_key]["error"] = str(e)
            report_error(f"Chinese/{platform}", e, {"video_subject": video_subject})


def send_chinese_platform_notification_email(platform_name, video_name):
    subject = f"Video Uploaded to {platform_name.capitalize()}"
    body = f"Your video '{video_name}' has been uploaded to {platform_name.capitalize()}!"
    send_email(subject, body, ["jack_hui@msn.com"])


def send_notification_email(video_id):
    subject = "YouTube Video Uploaded Successfully"
    body = f"Your video has been uploaded to YouTube!\n\nVideo ID: {video_id}\nURL: https://youtube.com/watch?v={video_id}"
    send_email(subject, body, ["jack_hui@msn.com"])


def send_instagram_notification_email():
    subject = "Instagram Reel Uploaded Successfully"
    body = "Your video has been uploaded to Instagram Reels!"
    send_email(subject, body, ["jack_hui@msn.com"])


if __name__ == "__main__":
    sys.exit(main())
