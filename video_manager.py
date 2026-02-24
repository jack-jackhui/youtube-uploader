# video_manager.py

import video_api_call
import openai_chatgpt
import os
from dotenv import load_dotenv
import requests
from article_manager import get_recent_articles
from topic_history import (
    get_recent_topic_titles,
    suggest_underrepresented_category,
    save_topic,
    detect_category
)
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
    source_url = None
    cross_feed_count = 1
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '')[:500]  # Limit content to prevent exceeding prompt length
        news_content += f"Title: {title}\nContent: {content}\n\n"
        # Track first article's source for saving
        if source_url is None:
            source_url = article.get('link', '')
            cross_feed_count = article.get('cross_feed_count', 1)

    # Get recent topics to avoid repetition
    recent_topics = get_recent_topic_titles(days=14)
    recent_topics_text = ""
    if recent_topics:
        recent_topics_text = "\n\nAVOID these recently covered topics (do NOT create similar titles):\n- " + "\n- ".join(recent_topics[:20])

    # Get suggested category if one is underrepresented
    preferred_category = suggest_underrepresented_category()
    preferred_text = ""
    if preferred_category:
        preferred_text = f"\n\nPREFERRED CATEGORY: Consider focusing on {preferred_category} topics if relevant articles exist, as this category has been underrepresented recently."

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
{recent_topics_text}
{preferred_text}

Examples of good trend-based question titles:
- "Is AI about to replace your favorite app?"
- "Why are tech giants suddenly betting on robots?"
- "Are we entering the age of AI agents?"

Return ONLY the video title question, nothing else.
"""
    else:
        # Chinese recent topics text
        recent_topics_cn = ""
        if recent_topics:
            recent_topics_cn = "\n\n避免这些最近涵盖的主题（不要创建类似的标题）：\n- " + "\n- ".join(recent_topics[:20])

        preferred_cn = ""
        if preferred_category:
            category_cn_map = {
                'ai': '人工智能', 'space': '太空', 'ev': '电动汽车',
                'semiconductor': '半导体', 'cybersecurity': '网络安全',
                'robotics': '机器人', 'quantum': '量子计算', 'crypto': '加密货币'
            }
            cat_name = category_cn_map.get(preferred_category, preferred_category)
            preferred_cn = f"\n\n首选类别：如果有相关文章，请考虑关注{cat_name}主题，因为该类别最近报道较少。"

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
{recent_topics_cn}
{preferred_cn}

只返回视频标题问题，不要其他内容。
"""

    # Generate video subject using OpenAI
    video_subject = openai_chatgpt.generate_video_subject(api_key, predefined_prompt)

    # Save the generated topic to history
    if video_subject:
        category = detect_category(video_subject, source_url)
        # Extract keywords from the topic
        keywords = ','.join(video_subject.replace('?', '').replace('!', '').split()[:5])
        save_topic(
            topic=video_subject,
            category=category,
            source_url=source_url,
            keywords=keywords,
            cross_feed_count=cross_feed_count
        )
        logger.info(f"Saved topic to history: {video_subject} (category: {category})")

    return video_subject

def generate_video_subject_from_prompt(api_key, language='en'):
    """Generate a video subject using a predefined prompt when no articles are available."""
    # Get recent topics to avoid repetition
    recent_topics = get_recent_topic_titles(days=14)
    recent_topics_text = ""
    if recent_topics:
        recent_topics_text = " AVOID these recently covered topics: " + ", ".join(recent_topics[:10]) + "."

    # Get suggested category if one is underrepresented
    preferred_category = suggest_underrepresented_category()
    preferred_text = ""
    if preferred_category:
        preferred_text = f" PREFERRED: Focus on {preferred_category} topics as this category has been underrepresented recently."

    if language == 'en':
        predefined_prompt = (
            "As a tech-focused content creator, generate a thought-provoking question-style video title "
            "about a current trending topic in technology. Focus on broader trends like: AI assistants and agents, "
            "robotics and automation, space technology, electric vehicles, quantum computing, AR/VR and spatial computing, "
            "cybersecurity threats, tech industry shifts, or breakthrough scientific discoveries. "
            "The title MUST be a compelling question that makes viewers curious. "
            "Do NOT include any political content or government-related topics. "
            f"Limit the number of characters to 100 or less.{recent_topics_text}{preferred_text} Return ONLY the question title."
        )
    else:
        recent_cn = ""
        if recent_topics:
            recent_cn = " 避免这些最近的主题: " + ", ".join(recent_topics[:10]) + "。"

        preferred_cn = ""
        if preferred_category:
            category_cn_map = {
                'ai': '人工智能', 'space': '太空', 'ev': '电动汽车',
                'semiconductor': '半导体', 'cybersecurity': '网络安全',
                'robotics': '机器人', 'quantum': '量子计算', 'crypto': '加密货币'
            }
            cat_name = category_cn_map.get(preferred_category, preferred_category)
            preferred_cn = f" 首选：关注{cat_name}主题。"

        predefined_prompt = (
            "作为科技领域的内容创作者，生成一个关于当前科技热门话题的问题式视频标题。"
            "关注更广泛的趋势，如：AI助手和智能体、机器人与自动化、太空科技、电动汽车、量子计算、"
            "AR/VR和空间计算、网络安全、科技行业变化或突破性科学发现。"
            "标题必须是一个引发好奇心的问题。"
            "不要包含任何政治内容或政府相关话题。"
            f"限制字符数不超过25个字。{recent_cn}{preferred_cn}只返回问题标题。"
        )

    video_subject = openai_chatgpt.generate_video_subject(api_key, predefined_prompt)

    # Save the generated topic to history
    if video_subject:
        category = detect_category(video_subject)
        keywords = ','.join(video_subject.replace('?', '').replace('!', '').split()[:5])
        save_topic(
            topic=video_subject,
            category=category,
            source_url=None,
            keywords=keywords,
            cross_feed_count=1
        )
        logger.info(f"Saved topic to history: {video_subject} (category: {category})")

    return video_subject

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