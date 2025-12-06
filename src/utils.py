
import json
import os


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SENT_IDS_FILE = os.path.join(DATA_DIR, "sent_ids.json")


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v is not None)
    return str(value)

def boost_score_by_keywords(item, keywords):
    title = _to_text(item.get("title", ""))
    summary = _to_text(item.get("summary", ""))
    text = (title + " " + summary).lower()
    return sum(2 for k in keywords if k in text)

def safe_get(d, key, default=""):
    v = d.get(key)
    return v if v is not None else default


def load_sent_ids():
    try:
        if not os.path.exists(SENT_IDS_FILE):
            return set()
        with open(SENT_IDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def save_sent_ids(sent_ids):
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(SENT_IDS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(sent_ids), f)
    except Exception:
        pass
