import video_api_call
import openai_chatgpt
import os
from dotenv import load_dotenv
import requests

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)


def generate_video_subject(api_key, language='en'):
    if language == 'en':
        predefined_prompt = "Act as a social media influencer, generate a single creative and engaging " \
                            "one line video subject for a tech-themed YouTube channel, ensure the video subject " \
                            "focused on one of the following topics: " \
                            "AI,Defi,ChatGPT, blockchain, Bitcoin, Ethereum, WEB3.0, Solana or Algorand." \
                            "Rotate between these topics frequently, but do not write more than one " \
                            "topics in a single video subject. Limit the number of characters to 100 or less."
    else:
        predefined_prompt = (
            "作为一名非常成功的社交媒体网红博主，为以科技主题的小红书频道生成一个有创意且吸引人的一句话视频主题，"
            "确保视频主题专注于以下主题之一："
            "人工智能（AI）、去中心化金融（DeFi）、ChatGPT、区块链、比特币、以太坊、Solana或Algorand。"
            "经常在这些主题之间轮换，但不要在单个视频主题中包含多个主题。限制字符数不超过25个字。"
        )
    return openai_chatgpt.generate_video_subject(api_key, predefined_prompt)


def process_video_subject(video_subject, language='en'):
    api_host = os.getenv('API_HOST')
    api_key = os.getenv('API_KEY')
    video_script = video_api_call.generate_video_script(api_key, api_host, video_subject, language, 1)
    video_terms = video_api_call.generate_video_terms(api_key, api_host, video_subject, video_script, 5, language)
    if video_terms:
        tags = video_terms
    else:
        tags = ["Future Tech", "tags"]
    return video_script, video_terms, tags


def generate_video_and_get_urls(video_subject, video_script, video_terms, voice_name, language='en'):
    api_host = os.getenv('API_HOST')
    api_key = os.getenv('API_KEY')

    # Generate the video and get the URLs
    video_urls = video_api_call.generate_video(api_key, api_host, video_subject, video_script, video_terms, voice_name, video_language=language)

    if not video_urls:
        print("Error in generating video. No URLs returned.")
        return None

    # Extract task_id from video URL for status checking
    original_video_url = video_urls['original']
    converted_video_url = video_urls.get('converted')
    task_id = original_video_url.split('/')[-2]

    # Check the status of the video generation task
    if video_api_call.check_task_status(api_key, api_host, task_id):
        # Return the public URLs
        converted_video_url_exist = check_remote_file_exists(converted_video_url)
        return original_video_url, converted_video_url if converted_video_url_exist else None
    else:
        print(f"Task {task_id} failed or was incomplete.")
        return None, None

def check_remote_file_exists(url):
    """
    Check if a remote file exists by sending a HEAD request to the URL.
    Returns True if the file exists, False otherwise.
    """
    try:
        response = requests.head(url)
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Error checking remote file: {e}")
        return False