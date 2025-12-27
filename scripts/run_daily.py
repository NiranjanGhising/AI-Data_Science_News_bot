import os
import sys
import datetime

# Ensure repository root is on sys.path so `src` package is importable
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.ingest_feeds import pull_company_posts
from src.ingest_arxiv import pull_arxiv
from src.ingest_semanticscholar import pull_s2
from src.ingest_crossref import pull_crossref
from src.ingest_pwc import pull_paperswithcode
from src.deliver_telegram import send_combined_daily_digest
from src.utils import boost_score_by_keywords, _to_text
from src.news_store import NewsStore, canonicalize_url
from src.link_summarizer import summarize_link

from src.opportunity.config_loader import load_scoring
from src.opportunity.pipeline import run_opportunity_pipeline, select_daily_items
from src.opportunity.storage import OpportunityStore

TOP_SOURCES = {
    "Google AI Blog",
    "DeepMind",
    "OpenAI News",
    "Microsoft Research",
    "Meta Engineering",
    "Anthropic News",
    "NVIDIA Developer Blog",
    "AWS Machine Learning Blog",
    "Apple Machine Learning Research",
    "Hugging Face Blog",
    "Mistral AI",
    "Cohere",
    "Databricks Blog",
    "Snowflake Blog",
    "GitHub Blog (AI)",
    "OpenAI Python SDK Releases",
    "OpenAI Node SDK Releases",
    "Transformers Releases",
    "Diffusers Releases",
    "LangChain Releases",
    "Ollama Releases",
    "vLLM Releases",
}

KEYWORDS = [
    "sdk","api","library","tool","agent","workflow","rag",
    "web dev","web development","app dev","application","developer","data engineering",
    # Model/documentation signals
    "release notes","changelog","migration","breaking change","version",
    "benchmark","eval","leaderboard",
    # Coding model signals
    "code","coding","swe-bench","repo","pull request","ide","copilot",
    # Image model signals
    "image","text-to-image","diffusion","photo","photoreal","flux","sdxl","stable diffusion"
]

def score(item):
    s = 0
    if item.get("source") in TOP_SOURCES: s += 3
    s += boost_score_by_keywords(item, KEYWORDS)
    if item.get("code_url"): s += 2
    title = _to_text(item.get("title")).lower()
    if any(k in title for k in ["release", "releases", "changelog", "release notes", "docs", "documentation"]):
        s += 1
    return s


def is_important(item) -> bool:
    title = _to_text(item.get("title")).lower()
    s = score(item)
    if item.get("source") in TOP_SOURCES and any(k in title for k in [
        "introducing", "announcing", "release", "launch", "preview", "update", "api", "sdk", "model"
    ]):
        return True
    return s >= 6

def main():
    items = []
    items += pull_company_posts()
    items += pull_arxiv()
    items += pull_s2()
    items += pull_crossref()
    items += pull_paperswithcode()

    uniq = {}
    for i in items:
        k = i.get("url") or i.get("arxiv_id") or i.get("DOI")
        if k and (k not in uniq or score(i) > score(uniq[k])):
            uniq[k] = i

    ranked = sorted(uniq.values(), key=score, reverse=True)

    # Persist AI send-state in SQLite to avoid repeats.
    ai_db_path = os.path.join(REPO_ROOT, "data", "news_radar.db")
    ai_store = NewsStore(ai_db_path)
    ai_store.init()

    for i in ranked:
        key = NewsStore.make_item_key(i)
        if not key:
            continue
        url = i.get("url") or i.get("URL") or ""
        canon = canonicalize_url(url)
        ai_store.upsert(
            item_key=key,
            canonical_url=canon,
            title=_to_text(i.get("title")).strip(),
            source=str(i.get("source") or "").strip(),
            url=str(url).strip(),
            published_at=str(i.get("date") or i.get("published") or "").strip() or None,
            score=int(score(i)),
            important=bool(is_important(i)),
        )

    # Select up to 8 AI items, allowing important repeats up to 3 total.
    selected_rows = ai_store.select_to_send(limit=8, max_important_reposts=3, min_repost_interval_hours=20)
    # Enrich with short summary + "why read" (cached in SQLite)
    ai_top = []
    for r in selected_rows:
        item_key = r["item_key"]
        title = r["title"]
        url = r["url"]
        source = r["source"]
        s = int(r["score"] or 0)

        cached_summary, cached_why, _fetched_at = ai_store.get_summary(item_key=item_key)
        if cached_summary and cached_why:
            link_summary = cached_summary
            why_read = cached_why
        else:
            ls = summarize_link(url, title_hint=title, source=source, score=s, keywords=KEYWORDS)
            link_summary = ls.summary
            why_read = ls.why_read
            if link_summary or why_read:
                ai_store.upsert_summary(
                    item_key=item_key,
                    link_summary=link_summary,
                    why_read=why_read,
                    fetched_at_iso=ls.fetched_at_iso,
                )

        ai_top.append(
            {
                "title": title,
                "url": url,
                "summary": link_summary,
                "why_read": why_read,
                "item_key": item_key,
            }
        )

    # Opportunity Radar (SQLite-backed) for dedup + notified state
    db_path = os.path.join(REPO_ROOT, "data", "opportunity_radar.db")
    store = OpportunityStore(db_path)
    scoring_cfg = load_scoring()
    opp_candidates = run_opportunity_pipeline(store=store)
    opp_daily = select_daily_items(opp_candidates, scoring_cfg)

    opp_top = []
    for i in opp_daily:
        opp_top.append(i.__dict__)

    if ai_top or opp_top:
        date_label = datetime.datetime.now().strftime("%Y-%m-%d")
        send_combined_daily_digest(
            date_label=date_label,
            ai_items=[{"title": x["title"], "url": x["url"], "summary": x.get("summary", ""), "why_read": x.get("why_read", "")} for x in ai_top],
            opp_items=opp_top,
        )

    # Mark AI items as notified (SQLite)
    if ai_top:
        ai_store.mark_notified([x["item_key"] for x in ai_top if x.get("item_key")])

    # Mark opportunities as notified (SQLite)
    if opp_daily:
        store.mark_notified([i.canonical_url for i in opp_daily if i.canonical_url])

if __name__ == "__main__":
    main()
