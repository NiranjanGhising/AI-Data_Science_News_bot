from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from . import connectors_atom, connectors_html, connectors_ics, connectors_json, connectors_rss
from .classify import classify_item
from .config_loader import load_keywords, load_scoring, load_sources
from .dedup import dedup_items
from .http_client import PoliteHttpClient
from .logging_utils import log_event
from .normalize import OpportunityItem, normalize_raw_item
from .score import score_item
from .storage import OpportunityStore
from .text_match import any_keyword, keyword_in_text


def _filter_negative(items: list[OpportunityItem], keywords_cfg: dict[str, Any]) -> list[OpportunityItem]:
    neg = [str(k).lower() for k in (keywords_cfg.get("negative_keywords") or [])]
    if not neg:
        return items
    out: list[OpportunityItem] = []
    for i in items:
        text = f"{i.title} {i.summary}"
        if any_keyword(text, neg):
            continue
        out.append(i)
    return out


def _filter_opportunity_like(items: list[OpportunityItem], keywords_cfg: dict[str, Any]) -> list[OpportunityItem]:
    """Keep only items that look like actual opportunities.

    Without this, general tech blog posts (e.g., security advisories) can dominate
    scoring and crowd out real programs/scholarships/certifications.
    """

    cat_kw: dict[str, list[str]] = (keywords_cfg.get("category_keywords") or {})
    category_signals: list[str] = []
    for kws in cat_kw.values():
        if isinstance(kws, list):
            category_signals += [str(k).lower() for k in kws if k]

    urgency = [str(k).lower() for k in (keywords_cfg.get("urgency_keywords") or [])]
    limited = [str(k).lower() for k in (keywords_cfg.get("limited_time_keywords") or [])]

    # Strong signals that usually indicate a real opportunity announcement.
    strong = [
        "apply",
        "apply by",
        "register",
        "registration",
        "deadline",
        "call for",
        "call for proposals",
        "cfp",
        "stipend",
        "grant",
        "scholarship",
        "fellowship",
        "internship",
        "intern",
        "certification",
        "certified",
        "exam",
        "voucher",
        "promo code",
        "early bird",
        "free",
    ]

    # If we have no signals, don't filter.
    if not (category_signals or urgency or limited or strong):
        return items

    # If a post matches only a broad category term (e.g., "program"), require a second
    # call-to-action to avoid classifying general blog posts as opportunities.
    broad_category_terms = {
        "program",
        "event",
        "summit",
        "conference",
        "course",
        "training",
        "workshop",
        "bootcamp",
        "challenge",
        "hackathon",
        "competition",
        "arcade",
    }
    secondary_cta = {
        "apply",
        "register",
        "registration",
        "deadline",
        "voucher",
        "free",
        "cfp",
        "call for",
        "call for proposals",
        "scholarship",
        "stipend",
        "grant",
    }

    out: list[OpportunityItem] = []
    for i in items:
        if i.deadline_at is not None:
            out.append(i)
            continue
        text = f"{i.title} {i.summary}"

        # Highest confidence: urgency/limited/strong signals.
        if any_keyword(text, urgency) or any_keyword(text, limited) or any_keyword(text, strong):
            out.append(i)
            continue

        # Category-only match: allow if it has at least one secondary CTA.
        matched_category = None
        for s in category_signals:
            if keyword_in_text(text, s):
                matched_category = s
                break
        if matched_category is None:
            continue

        if matched_category in broad_category_terms:
            if any_keyword(text, secondary_cta):
                out.append(i)
        else:
            out.append(i)
    return out


def run_opportunity_pipeline(
    *,
    store: Optional[OpportunityStore] = None,
    max_candidates: int = 250,
) -> list[OpportunityItem]:
    sources = [s for s in load_sources() if s.get("enabled") and s.get("url")]
    keywords_cfg = load_keywords()
    scoring_cfg = load_scoring()

    thresholds = scoring_cfg.get("thresholds") or {}
    urgent_days = int(thresholds.get("urgent_threshold_days", 7))
    window_days = int(thresholds.get("dedup_window_days", 60))
    jw_threshold = float(thresholds.get("fuzzy_jaro_winkler_threshold", 0.88))

    http = PoliteHttpClient()

    raw_items: list[dict[str, Any]] = []
    for s in sources:
        url = s.get("url")
        parser = (s.get("parser") or "rss").lower()
        try:
            if parser == "rss":
                raw_items += connectors_rss.fetch_rss(url, s)
            elif parser == "atom":
                raw_items += connectors_atom.fetch_atom(url, s)
            elif parser == "ics":
                raw_items += connectors_ics.fetch_ics(url, s, http)
            elif parser == "json":
                raw_items += connectors_json.fetch_json(url, s, http)
            elif parser == "html":
                raw_items += connectors_html.fetch_html(url, s, http)
            else:
                raw_items += connectors_rss.fetch_rss(url, s)
        except Exception as e:
            log_event("source_error", source_id=s.get("id"), url=url, error=str(e))

    normed = [normalize_raw_item(r) for r in raw_items]
    normed = [i for i in normed if i.title and i.content_url]
    normed = _filter_negative(normed, keywords_cfg)
    normed = _filter_opportunity_like(normed, keywords_cfg)

    deduped = dedup_items(normed, window_days=window_days, jw_threshold=jw_threshold)

    enriched: list[OpportunityItem] = []
    for i in deduped[:max_candidates]:
        i2 = classify_item(i, keywords_cfg, urgent_threshold_days=urgent_days)
        i3 = score_item(i2, keywords_cfg, scoring_cfg)
        enriched.append(i3)

    # Persist and filter 'fresh' (unnotified) items if store is provided.
    if store is not None:
        store.init()
        store.upsert_items(enriched)
        fresh = store.get_unnotified_items(limit=1000)
        # ensure we keep the latest computed scores/classification by overlaying on DB rows
        by_url = {i.canonical_url: i for i in enriched if i.canonical_url}
        out: list[OpportunityItem] = []
        for i in fresh:
            # Only include items that were seen in this run; otherwise older/noisy
            # unnotified rows can linger and crowd out real opportunities.
            src = by_url.get(i.canonical_url)
            if src is None:
                continue
            out.append(src)
        out_sorted = sorted(out, key=lambda x: x.score, reverse=True)
        log_event("pipeline_done", sources=len(sources), raw=len(raw_items), deduped=len(deduped), fresh=len(out_sorted))
        return out_sorted

    out_sorted = sorted(enriched, key=lambda x: x.score, reverse=True)
    log_event("pipeline_done", sources=len(sources), raw=len(raw_items), deduped=len(deduped), fresh=len(out_sorted))
    return out_sorted


def select_daily_items(items: list[OpportunityItem], scoring_cfg: dict[str, Any]) -> list[OpportunityItem]:
    limits = scoring_cfg.get("limits") or {}
    limit = int(limits.get("daily_max_items", 8))
    return items[:limit]


def select_priority_items(items: list[OpportunityItem], scoring_cfg: dict[str, Any]) -> list[OpportunityItem]:
    limits = scoring_cfg.get("limits") or {}
    limit = int(limits.get("priority_max_items", 3))
    urgent = [i for i in items if i.urgent]
    urgent_sorted = sorted(urgent, key=lambda x: x.score, reverse=True)
    return urgent_sorted[:limit]
