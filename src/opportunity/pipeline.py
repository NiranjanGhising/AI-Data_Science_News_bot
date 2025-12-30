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
from .program_tracker import load_tracked_programs, enrich_item_with_program_match
from .score import score_item
from .storage import OpportunityStore


def _filter_negative(items: list[OpportunityItem], keywords_cfg: dict[str, Any]) -> list[OpportunityItem]:
    neg = [str(k).lower() for k in (keywords_cfg.get("negative_keywords") or [])]
    if not neg:
        return items
    out: list[OpportunityItem] = []
    for i in items:
        text = f"{i.title} {i.summary}".lower()
        if any(k in text for k in neg):
            continue
        out.append(i)
    return out


def _is_likely_opportunity(item: OpportunityItem, keywords_cfg: dict[str, Any]) -> bool:
    """
    Check if an item is likely an opportunity worth showing.
    More permissive than before to avoid missing things.
    """
    text = f"{item.title} {item.summary}".lower()
    
    # Category keywords indicate relevance
    cat_kw: dict[str, list[str]] = keywords_cfg.get("category_keywords") or {}
    for kws in cat_kw.values():
        if isinstance(kws, list) and any(str(k).lower() in text for k in kws):
            return True
    
    # Urgency keywords indicate relevance
    urgency_kw = keywords_cfg.get("urgency_keywords") or []
    if any(str(k).lower() in text for k in urgency_kw):
        return True
    
    # Limited time keywords indicate relevance
    limited_kw = keywords_cfg.get("limited_time_keywords") or []
    if any(str(k).lower() in text for k in limited_kw):
        return True
    
    # Skill keywords - if it mentions skills we care about
    skill_kw = keywords_cfg.get("skill_keywords") or []
    if any(str(k).lower() in text for k in skill_kw):
        return True
    
    # Default: include it (we'd rather have more than miss things)
    return True


def run_opportunity_pipeline(
    *,
    store: Optional[OpportunityStore] = None,
    max_candidates: int = 500,  # Increased from 250
    include_all: bool = False,  # New flag to skip filtering
) -> list[OpportunityItem]:
    sources = [s for s in load_sources() if s.get("enabled") and s.get("url")]
    keywords_cfg = load_keywords()
    scoring_cfg = load_scoring()
    
    # Load tracked programs for enrichment
    tracked_programs, alert_settings = load_tracked_programs()

    thresholds = scoring_cfg.get("thresholds") or {}
    urgent_days = int(thresholds.get("urgent_threshold_days", 7))
    window_days = int(thresholds.get("dedup_window_days", 60))
    # Reduced threshold for less aggressive dedup (was 0.88)
    jw_threshold = float(thresholds.get("fuzzy_jaro_winkler_threshold", 0.92))

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
    
    log_event("pre_dedup", count=len(normed))

    deduped = dedup_items(normed, window_days=window_days, jw_threshold=jw_threshold)
    
    log_event("post_dedup", count=len(deduped))

    enriched: list[OpportunityItem] = []
    for i in deduped[:max_candidates]:
        i2 = classify_item(i, keywords_cfg, urgent_threshold_days=urgent_days)
        i3 = score_item(i2, keywords_cfg, scoring_cfg)
        # Enrich with tracked program matching
        i4 = enrich_item_with_program_match(i3, tracked_programs, alert_settings)
        enriched.append(i4)

    # Persist and filter 'fresh' (unnotified) items if store is provided.
    if store is not None:
        store.init()
        store.upsert_items(enriched)
        fresh = store.get_unnotified_items(limit=1000)
        # ensure we keep the latest computed scores/classification by overlaying on DB rows
        by_url = {i.canonical_url: i for i in enriched if i.canonical_url}
        out: list[OpportunityItem] = []
        for i in fresh:
            src = by_url.get(i.canonical_url)
            out.append(src if src is not None else i)
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
