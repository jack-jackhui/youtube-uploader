# article_manager.py

import re
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
from config import load_rss_feeds
import logging
import textstat
from urllib.parse import urlparse
from tranco import Tranco

logger = logging.getLogger(__name__)

# Initialize the Tranco list
latest_list = None

def initialize_tranco_list():
    """Initialize the Tranco List using the Tranco package."""
    global latest_list
    if latest_list is None:
        t = Tranco(cache=True, cache_dir='.tranco')
        date_to_try = datetime.today().strftime('%Y-%m-%d')
        retries = 3
        for _ in range(retries):
            try:
                latest_list = t.list(date=date_to_try)
                logger.info('Tranco list initialized.')
                logger.info(f'Using Tranco list for date: {date_to_try}')
                return latest_list
            except AttributeError:
                # Try previous day if latest fails
                date_to_try = (datetime.strptime(date_to_try, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            return t.list(date='latest-30')
        except Exception as e:
            logger.error(f"Fallback to monthly list failed: {e}")
            raise
    else:
        logger.info('Tranco list already initialized.')

def clean_text(text):
    """Remove HTML tags from the summary and return cleaned text."""
    return re.sub(r'<.*?>', '', text)

def get_full_text(url):
    """Retrieve the full text of an article from its URL using newspaper3k."""
    try:
        article = Article(url, browser_user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        logger.warning(f"Could not retrieve full text for {url}: {e}")
        return ""

def extract_domain(feed_url):
    """Extract the domain from a URL."""
    parsed_url = urlparse(feed_url)
    domain = parsed_url.netloc
    # Remove 'www.' prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def normalize_rank_to_score(rank):
    """Normalize the domain rank to a score between 1 and 10."""
    if rank is None or rank == -1:
        return 5  # Default score for domains not in the list
    else:
        # Normalize rank to score
        score = 10 - ((rank - 1) // 100000)
        return max(1, min(score, 10))

def get_source_score(feed_url):
    """Compute source score based on Tranco List domain rank using the Tranco package."""
    try:
        domain = extract_domain(feed_url)
        rank = latest_list.rank(domain)
        score = normalize_rank_to_score(rank)
        logger.debug(f"Domain {domain} has rank {rank}, normalized score {score}")
        return score
    except Exception as e:
        logger.warning(f"Error computing source score for {feed_url}: {e}")
        return 5  # Default score

def get_readability_score(text):
    """Compute readability score of the text."""
    try:
        score = textstat.flesch_reading_ease(text)
        # Normalize to a 0-10 scale
        normalized_score = max(0, min((score / 100) * 10, 10))
        return normalized_score
    except Exception as e:
        logger.warning(f"Could not compute readability score: {e}")
        return 5  # Default to average score

def get_recent_articles(max_articles=5):
    """Fetch recent articles from RSS feeds and select the highest value articles."""
    all_articles = []
    now = datetime.now()
    cutoff_date = now - timedelta(days=1)  # Get articles from the last day

    # Define AI and crypto keywords
    ai_keywords = [
        "AI", "Artificial Intelligence", "Machine Learning", "Deep Learning", "Neural Network",
        "Natural Language Processing", "NLP", "Computer Vision", "Robotics", "ChatGPT",
        "GPT-3", "GPT-4", "Reinforcement Learning", "Generative Adversarial Networks", "GAN",
        "Transformer", "BERT", "OpenAI", "TensorFlow", "PyTorch", "Cognitive Computing",
        "Data Science", "Algorithm", "Predictive Analytics", "Big Data", "Automation"
    ]

    crypto_keywords = [
        "Blockchain", "Bitcoin", "Ethereum", "Cryptocurrency", "DeFi", "Web 3.0",
        "Solana", "Algorand", "NFT", "Smart Contract", "Crypto"
    ]

    # Create a dictionary with keyword weights
    keywords_with_weights = {}

    # Assign weight 3 to AI keywords
    for kw in ai_keywords:
        keywords_with_weights[kw.lower()] = 4

    # Assign weight 1 to crypto keywords
    for kw in crypto_keywords:
        keywords_with_weights[kw.lower()] = 1

    # Initialize the Tranco list if not already done
    if latest_list is None:
        initialize_tranco_list()

    # Load RSS feeds from the configuration
    rss_feeds = load_rss_feeds()

    seen_links = set()

    for feed_url in rss_feeds:
        source_score = get_source_score(feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Parse the publish date
                if hasattr(entry, 'published_parsed'):
                    published_date = datetime(*entry.published_parsed[:6])
                else:
                    continue  # Skip if publish date is unavailable

                # Only consider articles published after the cutoff date
                if published_date > cutoff_date:
                    link = entry.link
                    if link in seen_links:
                        continue  # Skip duplicates
                    seen_links.add(link)

                    # Try to fetch the full text, falling back to summary if needed
                    full_text = get_full_text(link)
                    if not full_text:
                        # Check if entry has 'content' field with rich text
                        if hasattr(entry, 'content') and entry.content and 'value' in entry.content[0]:
                            raw_content = entry.content[0].value
                            full_text = clean_text(raw_content)
                        else:
                            # Fallback to summary if content isn't available
                            full_text = clean_text(entry.get('summary', 'Summary not available.'))

                    # Lowercase the text for case-insensitive matching
                    title_lower = entry.title.lower()
                    content_lower = full_text.lower()

                    # Calculate weighted keyword frequency in title and content
                    title_score = sum(title_lower.count(kw) * weight for kw, weight in keywords_with_weights.items())
                    content_score = sum(content_lower.count(kw) * weight for kw, weight in keywords_with_weights.items())

                    # Compute readability score
                    readability_score = get_readability_score(full_text)

                    # Assign weights
                    WEIGHT_TITLE = 3
                    WEIGHT_CONTENT = 2
                    WEIGHT_SOURCE = 1  # Adjusted if necessary
                    WEIGHT_READABILITY = 1

                    # Calculate the total score
                    total_score = (
                        (title_score * WEIGHT_TITLE) +
                        (content_score * WEIGHT_CONTENT) +
                        (source_score * WEIGHT_SOURCE) +
                        (readability_score * WEIGHT_READABILITY)
                    )

                    # Create article dictionary with score
                    article = {
                        "title": entry.title,
                        "content": full_text,
                        "link": link,
                        "published": published_date,
                        "score": total_score
                    }

                    # Add to the list if score is positive
                    if total_score > 0:
                        logger.debug(f"Article '{entry.title}' scored {total_score}")
                        all_articles.append(article)
        except Exception as e:
            logger.error(f"Failed to parse feed {feed_url}: {e}")

    # Sort articles by score in descending order
    sorted_articles = sorted(all_articles, key=lambda x: x['score'], reverse=True)

    # Select top max_articles
    top_articles = sorted_articles[:max_articles]

    logger.info(f"Total articles fetched: {len(top_articles)}")
    return top_articles