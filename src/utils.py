
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
