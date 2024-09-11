import video_api_call
import openai_chatgpt
import os
from dotenv import load_dotenv

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)


def generate_video_subject(api_key):
    predefined_prompt = "Act as a social media influencer, generate a single creative and engaging " \
                        "one line video subject for a tech-themed YouTube channel, ensure the video subject " \
                        "focused on one of the following topics: " \
                        "AI,Defi,ChatGPT, blockchain, Bitcoin, Ethereum, Solana or Algorand." \
                        "Rotate between these topics frequently, but do not write more than one " \
                        "topics in a single video subject. Limit the number of characters to 100 or less."

    return openai_chatgpt.generate_video_subject(api_key, predefined_prompt)


def process_video_subject(video_subject):
    api_host = os.getenv('API_HOST')
    api_key = os.getenv('API_KEY')
    video_script = video_api_call.generate_video_script(api_key, api_host, video_subject, '', 1)
    video_terms = video_api_call.generate_video_terms(api_key, api_host, video_subject, video_script, 5)
    if video_terms:
        tags = video_terms
    else:
        tags = ["Future Tech", "tags"]
    return video_script, video_terms, tags


def generate_and_download_video(video_subject, video_script, video_terms, voice_name):
    api_host = os.getenv('API_HOST')
    api_key = os.getenv('API_KEY')
    video_urls = video_api_call.generate_video(api_key, api_host, video_subject, video_script, video_terms, voice_name)

    if not video_urls:
        print("Error in generating video. No URLs returned.")
        return None

    # Extract task_id from video URL for status checking
    original_video_url = video_urls['original']
    converted_video_url = video_urls.get('converted')
    task_id = original_video_url.split('/')[-2]

    # Check the status of the video generation task
    if video_api_call.check_task_status(api_key, api_host, task_id):
        # If conversion exists, download both
        if converted_video_url:
            print(f"Converted video found: {converted_video_url}")
            converted_video_path = video_api_call.download_video(converted_video_url, video_subject,
                                                                 save_path="downloaded_videos")
            original_video_path = video_api_call.download_video(original_video_url, video_subject + "_original",
                                                                save_path="downloaded_videos")
            return original_video_path, converted_video_path
        else:
            # Only the original video exists
            print(f"Only original video found: {original_video_url}")
            original_video_path = video_api_call.download_video(original_video_url, video_subject,
                                                                save_path="downloaded_videos")
            return original_video_path, None
    return None