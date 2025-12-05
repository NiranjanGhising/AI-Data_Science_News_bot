
import requests

def pull_paperswithcode():
    url = "https://paperswithcode.com/api/v1/papers/"
    try:
        r = requests.get(url, params={"page_size": 20}, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []
