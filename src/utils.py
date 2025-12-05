
def boost_score_by_keywords(item, keywords):
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return sum(2 for k in keywords if k in text)

def safe_get(d, key, default=""):
    v = d.get(key)
    return v if v is not None else default
