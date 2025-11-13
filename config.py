# config.py

def load_rss_feeds(language='en'):
    """
    Returns a list of RSS feed URLs based on language.

    Args:
        language (str): 'en' for English feeds, 'zh' for Chinese feeds

    Returns:
        list: RSS feed URLs for the specified language
    """

    # English RSS feeds
    english_feeds = [
        # BestBlogs.dev - English feeds (last 3 days, high quality)
        'https://www.bestblogs.dev/en/feeds/rss?category=ai&timeFilter=3d&minScore=85',
        'https://www.bestblogs.dev/en/feeds/rss?category=product&timeFilter=3d&minScore=85',

        # Existing English sources
        'https://news.google.com/rss/search?q=blockchain&hl=en-US&gl=US&ceid=US:en',
        "https://ai.googleblog.com/feeds/posts/default",
        "https://www.microsoft.com/en-us/research/feed/",
        "https://www.ibm.com/blogs/research/feed/",
        "https://feeds.feedburner.com/DeepMind",
        "https://openai.com/blog/rss/",
        'https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en',
        "https://news.ycombinator.com/rss",
        "https://rss.cnn.com/rss/edition_business.rss",
        "https://cointelegraph.com/editors_pick_rss",
        "https://ai-techpark.com/category/ai/feed/",
        "https://aibusiness.com/rss.xml",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.reddit.com/r/artificial",
        "https://www.techrepublic.com/rssfeeds/topic/artificial-intelligence/",
        "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
        "https://feeds.bloomberg.com/technology/news.rss",
        "https://deepmind.com/blog/feed/basic/",
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
