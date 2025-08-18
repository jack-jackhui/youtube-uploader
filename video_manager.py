# video_manager.py

import video_api_call
import openai_chatgpt
import os
from dotenv import load_dotenv
import requests
from article_manager import get_recent_articles
import logging

logger = logging.getLogger(__name__)

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)


def generate_video_subject(api_key, language='en', articles=None):
    """Generate a video subject based on recent articles or a predefined prompt."""
    # Fetch the latest articles
    if articles is None:
        news_articles = get_recent_articles()

    if articles:
        # Generate video subject based on the fetched articles
        video_subject = generate_video_subject_from_articles(api_key, articles, language)
    else:
        # If no articles are found, fallback to the predefined prompt
        video_subject = generate_video_subject_from_prompt(api_key, language)

    return video_subject

def generate_video_subject_from_articles(api_key, articles, language='en'):
    """Generate a video subject based on recent articles using OpenAI's API."""
    # Prepare news content
    news_content = ''
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '')[:500]  # Limit content to prevent exceeding prompt length
        news_content += f"Title: {title}\nContent: {content}\n\n"

    # Define the prompt
    if language == 'en':
        predefined_prompt = f"""
As a social media influencer, create a single creative and engaging one-line video subject for a tech-themed YouTube channel that synthesizes insights from the following news articles:

{news_content}

Your video subject should capture an overarching theme, trend, or insightful perspective that connects these articles, providing a fresh take that goes beyond any single article.

Ensure the video subject focuses on one of the following topics: AI, DeFi, ChatGPT, blockchain, Bitcoin, Ethereum, Web 3.0, Solana, or Algorand.

Do not include more than one topic in a single video subject. Limit the number of characters to 100 or less.
"""
    else:
        predefined_prompt = f"""
作为一名社交媒体网红博主，基于以下新闻文章，为科技主题的小红书频道生成一个有创意且吸引人的一句话视频主题：

{news_content}
你的视频主题应捕捉这些文章所传达的整体主题、趋势或深刻见解，提供超越单篇文章的新鲜视角。
确保视频主题专注于最新的科技发展。不要在单个视频主题中包含多个主题。限制字符数不超过25个字。
"""

    # Generate video subject using OpenAI
    return openai_chatgpt.generate_video_subject(api_key, predefined_prompt)

def generate_video_subject_from_prompt(api_key, language='en'):
    """Generate a video subject using a predefined prompt."""
    if language == 'en':
        predefined_prompt = (
            "Act as a social media influencer, generate a single creative and engaging one-line video subject "
            "for a tech-themed YouTube channel. Ensure the video subject focuses on one of the following topics: "
            "AI, DeFi, ChatGPT, blockchain, Bitcoin, Ethereum, Web 3.0, Solana, or Algorand. Rotate between these topics "
            "frequently, but do not write more than one topic in a single video subject. Limit the number of characters "
            "to 100 or less."
        )
    else:
        predefined_prompt = (
            "作为一名非常成功的社交媒体网红博主，为以科技主题的小红书频道生成一个有创意且吸引人的一句话视频主题，"
            "确保视频主题专注于以下主题之一：人工智能（AI）、去中心化金融（DeFi）、ChatGPT、区块链、比特币、"
            "以太坊、Solana或Algorand。经常在这些主题之间轮换，但不要在单个视频主题中包含多个主题。"
            "限制字符数不超过25个字。"
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