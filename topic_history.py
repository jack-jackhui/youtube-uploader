# topic_history.py

import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# NocoDB Configuration
NOCODB_URL = "https://nocodb.jackhui.com.au"
NOCODB_API_TOKEN = "6XJhI5i7LEomXHPHlVBhXpWtJBTN3cYORVC_Okom"
TABLE_ID = "mgg9z4uyu7o52hp"

# API endpoints
API_BASE = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records"

# Headers for API requests
HEADERS = {
    "xc-token": NOCODB_API_TOKEN,
    "Content-Type": "application/json"
}

# Category keyword mappings for detection
CATEGORY_KEYWORDS = {
    'space': ['spacex', 'nasa', 'rocket', 'mars', 'starship', 'satellite', 'space station',
              'moon', 'blue origin', 'starlink', 'orbit', 'astronaut', 'launch'],
    'ev': ['tesla', 'ev', 'electric vehicle', 'battery', 'rivian', 'byd', 'waymo',
           'robotaxi', 'self-driving', 'autonomous', 'charging'],
    'semiconductor': ['nvidia', 'amd', 'intel', 'tsmc', 'chip', 'semiconductor',
                      'gpu', 'cpu', 'processor', 'silicon', 'foundry'],
    'cybersecurity': ['hack', 'breach', 'ransomware', 'cybersecurity', 'vulnerability',
                      'zero-day', 'malware', 'phishing', 'cyber attack', 'security flaw'],
    'robotics': ['robot', 'robotics', 'humanoid', 'boston dynamics', 'figure',
                 'optimus', 'automation', 'android'],
    'quantum': ['quantum', 'qubit', 'quantum computing', 'quantum computer'],
    'crypto': ['blockchain', 'bitcoin', 'ethereum', 'cryptocurrency', 'crypto',
               'defi', 'web3', 'nft'],
    'arvr': ['ar', 'vr', 'augmented reality', 'virtual reality', 'meta quest',
             'vision pro', 'mixed reality', 'spatial computing', 'metaverse'],
    'ai': ['ai', 'artificial intelligence', 'machine learning', 'deep learning',
           'chatgpt', 'gpt', 'llm', 'large language model', 'generative ai',
           'openai', 'anthropic', 'claude', 'gemini', 'neural network']
}


def init_table():
    """
    Check if the table exists and is accessible.
    The table is already created via NocoDB API, this function verifies connectivity.
    """
    try:
        response = requests.get(
            API_BASE,
            headers=HEADERS,
            params={"limit": 1}
        )
        if response.status_code == 200:
            logger.info("NocoDB topic_history table connection verified")
            return True
        else:
            logger.error(f"Failed to connect to NocoDB table: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to NocoDB: {e}")
        return False


def get_recent_topics(days=14):
    """
    Fetch topics from the last N days.

    Args:
        days (int): Number of days to look back (default 14)

    Returns:
        list: List of topic dictionaries
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        # Use ISO 8601 format for NocoDB
        cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # NocoDB filter for generated_at >= cutoff_date
        response = requests.get(
            API_BASE,
            headers=HEADERS,
            params={
                "where": f"(generated_at,ge,{cutoff_str})",
                "sort": "-generated_at",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            topics = data.get("list", [])
            logger.info(f"Retrieved {len(topics)} topics from the last {days} days")
            return topics
        else:
            # If filter fails, try fetching all and filtering locally
            logger.warning(f"Filter query failed: {response.status_code}, trying without filter...")
            response = requests.get(
                API_BASE,
                headers=HEADERS,
                params={
                    "sort": "-generated_at",
                    "limit": 100
                }
            )
            if response.status_code == 200:
                data = response.json()
                all_topics = data.get("list", [])
                # Filter locally
                filtered_topics = []
                for topic in all_topics:
                    gen_at = topic.get("generated_at")
                    if gen_at:
                        try:
                            topic_date = datetime.fromisoformat(gen_at.replace('Z', '+00:00').replace('+00:00', ''))
                            if topic_date >= cutoff_date:
                                filtered_topics.append(topic)
                        except (ValueError, TypeError):
                            filtered_topics.append(topic)  # Include if can't parse
                logger.info(f"Retrieved {len(filtered_topics)} topics from the last {days} days (local filter)")
                return filtered_topics
            logger.error(f"Failed to fetch recent topics: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching recent topics: {e}")
        return []


def save_topic(topic, category, source_url, keywords, cross_feed_count=1):
    """
    Save a new topic to the history table.

    Args:
        topic (str): The video topic/title
        category (str): Category classification
        source_url (str): Source article URL
        keywords (str): Comma-separated keywords
        cross_feed_count (int): Number of feeds covering this story

    Returns:
        bool: True if saved successfully
    """
    try:
        # Extract domain from source URL
        source_domain = ""
        if source_url:
            parsed = urlparse(source_url)
            source_domain = parsed.netloc.replace("www.", "")

        record = {
            "topic": topic,
            "category": category,
            "source_article_url": source_url if source_url else None,
            "source_domain": source_domain,
            "keywords": keywords,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cross_feed_count": cross_feed_count
        }

        response = requests.post(
            API_BASE,
            headers=HEADERS,
            json=record
        )

        if response.status_code in [200, 201]:
            logger.info(f"Saved topic to history: {topic[:50]}...")
            return True
        else:
            logger.error(f"Failed to save topic: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error saving topic: {e}")
        return False


def get_category_coverage(days=7):
    """
    Count topics per category over the last N days.

    Args:
        days (int): Number of days to analyze (default 7)

    Returns:
        dict: Category name -> count mapping
    """
    try:
        topics = get_recent_topics(days=days)

        # Count categories
        category_counts = {}
        for topic in topics:
            category = topic.get("category", "general")
            category_counts[category] = category_counts.get(category, 0) + 1

        # Ensure all known categories are represented
        all_categories = ['ai', 'space', 'ev', 'semiconductor', 'cybersecurity',
                         'robotics', 'quantum', 'crypto', 'arvr', 'general']
        for cat in all_categories:
            if cat not in category_counts:
                category_counts[cat] = 0

        logger.info(f"Category coverage (last {days} days): {category_counts}")
        return category_counts
    except Exception as e:
        logger.error(f"Error getting category coverage: {e}")
        return {}


def suggest_underrepresented_category():
    """
    Find the least-covered category to suggest for the next video.

    Returns:
        str: The category with the least coverage, or None if can't determine
    """
    try:
        coverage = get_category_coverage(days=7)

        if not coverage:
            return None

        # Exclude 'general' from consideration for suggestions
        filtered_coverage = {k: v for k, v in coverage.items() if k != 'general'}

        if not filtered_coverage:
            return None

        # Find the category with minimum count
        min_category = min(filtered_coverage, key=filtered_coverage.get)
        min_count = filtered_coverage[min_category]

        logger.info(f"Suggested underrepresented category: {min_category} (count: {min_count})")
        return min_category
    except Exception as e:
        logger.error(f"Error suggesting category: {e}")
        return None


def detect_category(topic, source_url=None):
    """
    Detect the category of a topic based on keywords.

    Args:
        topic (str): The video topic/title
        source_url (str): Optional source URL for additional context

    Returns:
        str: Detected category or 'general' if no match
    """
    import re
    topic_lower = topic.lower()

    # Also check source URL domain for hints
    source_domain = ""
    if source_url:
        parsed = urlparse(source_url)
        source_domain = parsed.netloc.lower()

    # Check each category's keywords with word boundary matching
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            # Use word boundary matching to avoid partial matches
            # e.g., "ev" should not match "developers"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, topic_lower) or re.search(pattern, source_domain):
                return category

    return 'general'


def get_recent_topic_titles(days=14):
    """
    Get just the topic titles from recent history for prompt injection.

    Args:
        days (int): Number of days to look back

    Returns:
        list: List of topic title strings
    """
    topics = get_recent_topics(days=days)
    return [t.get("topic", "") for t in topics if t.get("topic")]


def is_topic_similar(new_topic, threshold=0.5):
    """
    Check if a new topic is too similar to recent ones.
    Uses simple keyword overlap for similarity detection.

    Args:
        new_topic (str): The proposed new topic
        threshold (float): Similarity threshold (0-1)

    Returns:
        bool: True if topic is too similar to recent ones
    """
    recent_titles = get_recent_topic_titles(days=14)

    new_words = set(new_topic.lower().split())

    for title in recent_titles:
        title_words = set(title.lower().split())
        if not title_words:
            continue

        # Calculate Jaccard similarity
        intersection = len(new_words & title_words)
        union = len(new_words | title_words)

        if union > 0:
            similarity = intersection / union
            if similarity >= threshold:
                logger.warning(f"Topic '{new_topic[:30]}...' is similar to '{title[:30]}...' (similarity: {similarity:.2f})")
                return True

    return False
