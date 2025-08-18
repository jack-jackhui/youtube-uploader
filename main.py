# main.py
# import sys
import asyncio
import argparse
import video_api_call
from youtube_manager import authenticate_youtube, upload_video
# import google_sheets
# import openai_chatgpt
from voice_manager import get_last_used_voice, get_random_voice, store_last_used_voice
from video_manager import generate_video_subject, process_video_subject, generate_video_and_get_urls
# import json
from dotenv import load_dotenv
import os
import test_youtube
from email_notifier import send_email
from instagram_publisher import publish_video_to_instagram
from main_cn import main as chinese_uploader_main

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)


# Now you can access these variables using os.getenv
api_host = os.getenv('API_HOST')
api_key = os.getenv('API_KEY')

openai_api_key = os.getenv('OPEN_AI_KEY')  # Retrieve securely

ig_user_id = os.getenv("IG_USER_ID")  # Instagram User ID
ig_access_token = os.getenv("IG_ACCESS_TOKEN")  # Instagram Access Token

print("main.py is starting up")

def main():
    print("Entered main()")
    parser = argparse.ArgumentParser(description="Generate and upload videos to various platforms.")
    parser.add_argument('--language', choices=['en', 'zh'], default='en', help="Language of the video ('en' for English, 'zh' for Chinese).")
    args = parser.parse_args()
    print("Args parsed:", args)

    language = args.language

    # Main process flow
    last_voice = get_last_used_voice(language)
    voice_name = get_random_voice(last_voice, language)
    store_last_used_voice(voice_name)  # Store the current voice for next time

    video_subject = generate_video_subject(openai_api_key, language)
    if video_subject:
        video_script, video_terms, tags = process_video_subject(video_subject, language)
        # Generate and download the video (both original and potentially converted)
        video_urls = generate_video_and_get_urls(video_subject, video_script, video_terms, voice_name, language)

        if video_urls:
            original_video_url, converted_video_url = video_urls

            if language == 'en':
                # Check the environment variable to determine whether to skip YouTube upload
                skip_yt_upload = os.getenv("SKIP_YT_UPLOAD", "false").lower() == "true"

                if not skip_yt_upload:
                    # Download the original video
                    print(f"Downloading original video for YouTube upload: {original_video_url}")
                    original_video_path = video_api_call.download_video(original_video_url, video_subject, save_path="downloaded_videos")

                    # Upload original video to YouTube
                    youtube = authenticate_youtube()
                    upload_response = upload_video(youtube, original_video_path, video_subject, video_subject, tags)

                    if upload_response:
                        # Send email notification upon successful YouTube upload
                        send_notification_email(upload_response['id'])
                        print(f"Video uploaded successfully to YouTube. Video ID: {upload_response['id']}")
                else:
                    print("YouTube upload skipped as per configuration.")

                # Check the environment variable to determine whether to skip Instagram upload
                skip_ig_upload = os.getenv("SKIP_IG_UPLOAD", "false").lower() == "true"

                if not skip_ig_upload:
                    # If converted video exists, upload it to Instagram
                    if converted_video_url:
                        print(f"Uploading converted video to Instagram: {converted_video_url}")
                        instagram_upload_success = publish_video_to_instagram(ig_user_id, converted_video_url, ig_access_token)
                    else:
                        # If no converted video, upload the original video to Instagram
                        print(f"No converted video found. Uploading original video to Instagram: {original_video_url}")
                        instagram_upload_success = publish_video_to_instagram(ig_user_id, original_video_url, ig_access_token)

                    if instagram_upload_success:
                        send_instagram_notification_email()
                        print("Email notification sent for successful Instagram upload.")
                    else:
                        print("Instagram upload failed. No email notification sent.")
                else:
                    print("Instagram upload skipped as per configuration.")
            elif language == 'zh':
                # Upload to Chinese platforms
                # Download the original video for uploading to Chinese platforms
                print(f"Downloading original video for Chinese platforms upload: {original_video_url}")
                original_video_path = video_api_call.download_video(original_video_url, video_subject,
                                                                    save_path="downloaded_videos")

                # Call the Chinese uploader
                asyncio.run(upload_to_chinese_platforms(original_video_path, video_subject, video_subject, tags))
            else:
                print(f"Unsupported language: {language}")
        else:
            print("Failed to generate or download the video.")
    else:
        print("Failed to generate video subject.")

# Make the upload_to_chinese_platforms async
async def upload_to_chinese_platforms(video_path, video_subject, video_script, tags):
    """
    Uploads the video to Chinese platforms using the imported async uploader.
    """
    # platforms = ['bili', 'douyin', 'xhs']
    platforms = ['xhs']
    for platform in platforms:
        try:
            platform_name = platform
            video_url = ""  # Provide actual URL if available
            video_name = video_subject
            cover_path = None  # Provide cover image path if available
            description = video_script
            topics = tags
            headless = True  # Set to True if you prefer headless mode

            # Call the asynchronous function
            upload_success = await chinese_uploader_main(
                platform_name=platform_name,
                video_url=video_url,
                video_path=video_path,
                video_name=video_name,
                cover_path=cover_path,
                description=description,
                topics=topics,
                headless=headless
            )
            if upload_success:
                print(f"Video uploaded successfully to {platform_name}.")
                # Send email notification after successful upload
                send_chinese_platform_notification_email(platform_name, video_name)
            else:
                print(f"Failed to upload video to {platform_name}. No email will be sent.")

        except Exception as e:
            print(f"An error occurred while uploading to {platform}: {e}")

def send_chinese_platform_notification_email(platform_name, video_name):
    """
    Sends an email notification after successfully uploading a video to a Chinese platform.
    """
    subject = f"Your Latest Video Uploaded Successfully to {platform_name.capitalize()}"
    body = f"Your video '{video_name}' has been uploaded successfully to {platform_name.capitalize()}!"
    send_email(subject, body, ["jack_hui@msn.com"])
def send_notification_email(video_id):
    subject = "Your Latest Youtube Video Uploaded Successfully"
    body = f"Your video has been uploaded successfully to Youtube! Video ID: {video_id}"
    send_email(subject, body, ["jack_hui@msn.com"])

def send_instagram_notification_email():
    subject = "Your Latest Instagram Video Uploaded Successfully"
    body = "Your video has been uploaded successfully to Instagram!"
    send_email(subject, body, ["jack_hui@msn.com"])

if __name__ == '__main__':
    # Uncomment the line below to test YouTube upload functionality independently.
    #test_youtube.test_youtube_upload()

    main()
