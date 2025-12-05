
import feedparser

ARXIV_URL = (
    "https://export.arxiv.org/api/query?"
    "search_query=cat:cs.LG+OR+cat:cs.CL+OR+cat:stat.ML"
    "&sortBy=submittedDate&sortOrder=descending&max_results=50"
)

def pull_arxiv():
    feed = feedparser.parse(ARXIV_URL)
    items = []
    for e in feed.entries:
        items.append({
            "title": e.title,
            "summary": e.summary,
            "url": e.link,
            "date": e.published,
            "source": "arXiv",
            "arxiv_id": e.id.split("/")[-1]
        })
    return items
