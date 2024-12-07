# test_article_manager.py

import logging
from article_manager import get_recent_articles

# Set up logging to output to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting test of get_recent_articles()")
        articles = get_recent_articles(max_articles=9999)

        if articles:
            logger.info(f"Fetched {len(articles)} articles:")
            for idx, article in enumerate(articles, start=1):
                logger.info(f"\nArticle {idx}:")
                logger.info(f"Title: {article['title']}")
                logger.info(f"Score: {article['score']}")
                logger.info(f"Published: {article['published']}")
                logger.info(f"Link: {article['link']}")
                logger.info(f"Content Snippet: {article['content'][:200]}...")  # Print first 200 characters
        else:
            logger.warning("No articles were fetched.")
    except Exception as e:
        logger.error(f"An error occurred during the test: {e}")

if __name__ == "__main__":
    main()