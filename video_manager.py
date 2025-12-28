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
        news_articles = get_recent_articles(language=language)

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
As a tech-focused content creator, analyze these recent news articles and identify the dominant trend or theme connecting them:

{news_content}

Based on your analysis:
1. First, identify the key trend, technology, or development that appears across multiple articles
2. Then, create a compelling question-style video title that captures this trend

Requirements:
- The title MUST be a thought-provoking question that makes viewers curious
- Focus on the underlying TREND, not specific product names (unless it's genuinely the biggest story)
- Synthesize insights across articles rather than focusing on just one
- Keep within tech/AI/innovation space but don't force-fit unrelated topics
- Do NOT include any political content or government-related topics
- Maximum 100 characters

Examples of good trend-based question titles:
- "Is AI about to replace your favorite app?"
- "Why are tech giants suddenly betting on robots?"
- "Are we entering the age of AI agents?"

Return ONLY the video title question, nothing else.
"""
    else:
        predefined_prompt = f"""
作为科技领域的内容创作者，分析以下新闻文章并识别它们之间的主要趋势或主题：

{news_content}

基于你的分析：
1. 首先，识别多篇文章中出现的关键趋势、技术或发展
2. 然后，创建一个引人入胜的问题式视频标题来捕捉这一趋势

要求：
- 标题必须是一个引发好奇心的问题
- 关注潜在趋势，而非具体产品名称（除非它确实是最大的热点）
- 综合多篇文章的见解，而不仅仅关注一篇
- 保持在科技/AI/创新领域，但不要强行关联无关主题
- 不要包含任何政治内容或政府相关话题
- 最多25个字符

只返回视频标题问题，不要其他内容。
"""

    # Generate video subject using OpenAI
    return openai_chatgpt.generate_video_subject(api_key, predefined_prompt)

def generate_video_subject_from_prompt(api_key, language='en'):
    """Generate a video subject using a predefined prompt when no articles are available."""
    if language == 'en':
        predefined_prompt = (
            "As a tech-focused content creator, generate a thought-provoking question-style video title "
            "about a current trending topic in technology. Focus on broader trends like: AI assistants and agents, "
            "robotics and automation, space technology, electric vehicles, quantum computing, AR/VR and spatial computing, "
            "cybersecurity threats, tech industry shifts, or breakthrough scientific discoveries. "
            "The title MUST be a compelling question that makes viewers curious. "
            "Do NOT include any political content or government-related topics. "
            "Limit the number of characters to 100 or less. Return ONLY the question title."
        )
    else:
        predefined_prompt = (
            "作为科技领域的内容创作者，生成一个关于当前科技热门话题的问题式视频标题。"
            "关注更广泛的趋势，如：AI助手和智能体、机器人与自动化、太空科技、电动汽车、量子计算、"
            "AR/VR和空间计算、网络安全、科技行业变化或突破性科学发现。"
            "标题必须是一个引发好奇心的问题。"
            "不要包含任何政治内容或政府相关话题。"
            "限制字符数不超过25个字。只返回问题标题。"
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