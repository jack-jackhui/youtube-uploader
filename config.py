# config.py

def load_rss_feeds(language='en'):
    """
    Returns a list of RSS feed URLs based on language.

    Args:
        language (str): 'en' for English feeds, 'zh' for Chinese feeds

    Returns:
        list: RSS feed URLs for the specified language
    """

    # English RSS feeds - Diverse tech categories
    english_feeds = [
        # AI/ML (reduced, keep best)
        "https://openai.com/blog/rss/",
        "https://feeds.feedburner.com/DeepMind",
        "https://venturebeat.com/category/ai/feed/",

        # Space & Aerospace
        "https://www.spacenews.com/feed/",
        "https://www.nasaspaceflight.com/feed/",
        "https://www.space.com/feeds/all",

        # Electric Vehicles & Auto
        "https://electrek.co/feed/",
        "https://insideevs.com/rss/news/",

        # Semiconductors & Hardware
        "https://www.anandtech.com/rss/",
        "https://www.tomshardware.com/feeds/all",

        # Cybersecurity
        "https://krebsonsecurity.com/feed/",
        "https://www.bleepingcomputer.com/feed/",

        # Robotics
        "https://www.therobotreport.com/feed/",

        # Quantum Computing
        "https://quantumcomputingreport.com/feed/",

        # General Tech (broad coverage)
        "https://news.ycombinator.com/rss",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/",
        "https://arstechnica.com/feed/",
        "https://feeds.bloomberg.com/technology/news.rss",
    ]

    # Chinese RSS feeds
    chinese_feeds = [
        # BestBlogs.dev - Chinese feeds (last 3 days, high quality)
        'https://www.bestblogs.dev/zh/feeds/rss?category=ai&timeFilter=3d&minScore=85',
        'https://www.bestblogs.dev/zh/feeds/rss?category=product&timeFilter=3d&minScore=85',
        'https://www.bestblogs.dev/zh/feeds/rss?category=business&timeFilter=3d&minScore=85',

        # Chinese news and tech sources
        'https://news.google.com/rss/search?q=人工智能&hl=zh-CN&gl=CN&ceid=CN:zh-Hans',
        'https://news.google.com/rss/search?q=科技&hl=zh-CN&gl=CN&ceid=CN:zh-Hans',
        'https://news.google.com/rss/search?q=游戏&hl=zh-CN&gl=CN&ceid=CN:zh-Hans',
    ]

    return chinese_feeds if language == 'zh' else english_feeds
