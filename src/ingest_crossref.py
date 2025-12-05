
import requests

def pull_crossref():
    url = "https://api.crossref.org/works"
    params = {
        "query": "artificial intelligence OR machine learning OR data engineering",
        "filter": "from-pub-date:2025-11-01",
        "rows": 20,
        "select": "DOI,title,created,URL,author,container-title"
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()["message"]["items"]
    except Exception:
        return []
