import os
import sys
import datetime

# Ensure repository root is on sys.path so `src` package is importable
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from src.ingest_feeds import pull_company_posts
from src.deliver_telegram import send_combined_priority_alert
from src.news_store import NewsStore, canonicalize_url

from src.opportunity.config_loader import load_scoring
from src.opportunity.pipeline import run_opportunity_pipeline, select_priority_items
from src.opportunity.storage import OpportunityStore


PRIORITY_SOURCES = {
    "Google AI Blog",
    "DeepMind",
    "OpenAI News",
    "Microsoft Research",
    "Meta Engineering",
    "Anthropic News",
    "NVIDIA Developer Blog",
    "AWS Machine Learning Blog",
    "Apple Machine Learning Research",
    "Mistral AI",
    "Cohere",
    "OpenAI Python SDK Releases",
    "OpenAI Node SDK Releases",
}

def is_quiet_hours_utc():
    # Quiet hours in NPT (22:00-07:00). Approx skip in UTC:
    # NPT = UTC+05:45 → quiet hours ≈ 16:15–01:15 UTC.
    # We’ll skip hours 16..23 and 0..1 for safety.
    utc_hour = datetime.datetime.now(datetime.UTC).hour
    return utc_hour in list(range(16, 24)) + [0, 1]

def main():
    if os.getenv("FORCE_RUN") == "1":
        pass
    elif is_quiet_hours_utc():
        print("Quiet hours; skipping alerts.")
        return

    posts = pull_company_posts()
    big = [
        p
        for p in posts
        if (p.get("source") in PRIORITY_SOURCES)
        and any(
            k in p["title"].lower()
            for k in [
                "introducing",
                "announcing",
                "release",
                "model",
                "api",
                "sdk",
                "agent",
                "workflow",
                "preview",
                "launch",
                "update",
                "changelog",
                "release notes",
            ]
        )
    ]

    # AI/Research priority items: SQLite-backed send-state
    ai_db_path = os.path.join(REPO_ROOT, "data", "news_radar.db")
    ai_store = NewsStore(ai_db_path)
    ai_store.init()

    for p in big:
        key = NewsStore.make_item_key(p)
        if not key:
            continue
        url = p.get("url") or p.get("URL") or ""
        ai_store.upsert(
            item_key=key,
            canonical_url=canonicalize_url(url),
            title=str(p.get("title") or "").strip(),
            source=str(p.get("source") or "").strip(),
            url=str(url).strip(),
            published_at=str(p.get("date") or p.get("published") or "").strip() or None,
            score=10,
            important=True,
        )

    selected_ai = ai_store.select_to_send(
        limit=3,
        require_important=True,
        max_important_reposts=3,
        min_repost_interval_hours=8,
    )

    # Opportunity urgent alerts (SQLite-backed)
    db_path = os.path.join(REPO_ROOT, "data", "opportunity_radar.db")
    store = OpportunityStore(db_path)
    scoring_cfg = load_scoring()
    opp_candidates = run_opportunity_pipeline(store=store)
    opp_urgent = select_priority_items(opp_candidates, scoring_cfg)

    ai_top = [{"title": r["title"], "url": r["url"], "item_key": r["item_key"]} for r in selected_ai]

    opp_top = []
    for i in opp_urgent:
        opp_top.append(i.__dict__)

    if ai_top or opp_top:
        send_combined_priority_alert(
            ai_items=[{"title": x["title"], "url": x["url"]} for x in ai_top],
            opp_items=opp_top,
        )

    if ai_top:
        ai_store.mark_notified([x["item_key"] for x in ai_top if x.get("item_key")])

    # Mark opportunities as notified (SQLite)
    if opp_urgent:
        store.mark_notified([i.canonical_url for i in opp_urgent if i.canonical_url])

if __name__ == "__main__":
    main()
