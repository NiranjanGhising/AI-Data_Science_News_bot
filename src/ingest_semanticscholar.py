
import requests

def pull_s2(query="large language models OR data science OR data engineering"):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "fields": "title,authors,abstract,year,venue,openAccessPdf,externalIds,url",
        "limit": 20
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return []
