
import feedparser

FEEDS = {
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "DeepMind": "https://deepmind.google/blog/feed/",
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "Meta Engineering": "https://engineering.fb.com/feed",
}

def pull_company_posts():
    items = []
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for e in feed.entries[:15]:
            items.append({
                "title": e.title,
                "summary": getattr(e, "summary", ""),
                "url": e.link,
                "date": getattr(e, "published", getattr(e, "updated", "")),
                "source": source
            })
    return items
