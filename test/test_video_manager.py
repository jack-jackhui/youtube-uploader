# test_video_manager.py

import logging
import os
import sys
from dotenv import load_dotenv
# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, root_dir)  # Add root directory to search path

# Import the necessary functions
from video_manager import generate_video_subject, process_video_subject
from article_manager import get_recent_articles  # Import get_recent_articles

# Set up logging to output to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Determine the root directory (parent directory of this script's directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, '..'))

    # Determine which .env file to load (same as in main.py)
    env = os.getenv('ENV', 'development')
    dotenv_filename = f'.env.{env}'

    # Construct the full path to the .env file in the root directory
    dotenv_path = os.path.join(root_dir, dotenv_filename)

    # Load the environment variables from the chosen file
    load_dotenv(dotenv_path=dotenv_path)

    # Retrieve environment variables
    api_host = os.getenv('API_HOST')
    api_key = os.getenv('API_KEY')
    openai_api_key = os.getenv('OPEN_AI_KEY')

    # Check if the necessary environment variables are set
    missing_vars = []
    if not openai_api_key:
        missing_vars.append('OPEN_AI_KEY')
    if not api_key:
        missing_vars.append('API_KEY')
    if not api_host:
        missing_vars.append('API_HOST')
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}. Please set them in your {dotenv_filename} file in the root directory.")
        return

    # Set the language ('en' for English or 'zh' for Chinese)
    language = 'zh'  # Change to 'en' if needed

    # Fetch the latest articles
    logger.info("Fetching latest articles...")
    news_articles = get_recent_articles()

    if news_articles:
        logger.info(f"Fetched {len(news_articles)} articles:")
        for idx, article in enumerate(news_articles, start=1):
            title = article.get('title', 'No Title')
            logger.info(f"Article {idx} Title: {title}")
    else:
        logger.warning("No articles were fetched.")
        return

    # Generate the video subject using the fetched articles
    logger.info("Generating video subject...")
    video_subject = generate_video_subject(openai_api_key, language, articles=news_articles)
    if video_subject:
        logger.info(f"Video Subject: {video_subject}")
    else:
        logger.error("Failed to generate video subject.")
        return

    # Process the video subject to get the script and terms
    
    logger.info("Processing video subject to generate script and terms...")
    video_script, video_terms, tags = process_video_subject(video_subject, language)
    if video_script and video_terms:
        logger.info(f"Video Script: {video_script}")
        logger.info(f"Video Terms: {video_terms}")
        logger.info(f"Tags: {tags}")
    else:
        logger.error("Failed to generate video script and terms.")
    
if __name__ == "__main__":
    main()