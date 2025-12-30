from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from .normalize import OpportunityItem
from .text_match import any_keyword


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _text(item: OpportunityItem) -> str:
    return f"{item.title} {item.summary}".lower()


def _company_reputation(tags: tuple[str, ...]) -> float:
    t = {s.lower() for s in tags}
    if any(x in t for x in {"google", "deepmind", "openai", "microsoft", "aws", "nvidia", "oracle", "github", "cloudflare", "ibm", "redhat", "intel", "meta"}):
        return 1.0
    if any(x in t for x in {"outreachy", "mlh"}):
        return 0.9
    return 0.6


def _skill_relevance(item: OpportunityItem, keywords_cfg: dict[str, Any]) -> float:
    kws = [str(k).lower() for k in (keywords_cfg.get("skill_keywords") or [])]
    if not kws:
        return 0.5
    text = _text(item)
    hits = sum(1 for k in kws if k in text)
    return _clamp01(hits / 6.0)


def _benefit_value(item: OpportunityItem, keywords_cfg: dict[str, Any]) -> float:
    limited = [str(k).lower() for k in (keywords_cfg.get("limited_time_keywords") or [])]
    urgency = [str(k).lower() for k in (keywords_cfg.get("urgency_keywords") or [])]
    text = _text(item)

    value = 0.4
    if any_keyword(text, limited):
        value += 0.4
    if "scholarship" in text or "stipend" in text or "grant" in text:
        value += 0.3
    if "voucher" in text or "free" in text:
        value += 0.2
    if any_keyword(text, urgency):
        value += 0.1
    return _clamp01(value)


def _timeliness(item: OpportunityItem) -> float:
    # Higher if recently published and/or deadline soon.
    score = 0.4
    now = _now_utc()

    if item.published_at is not None:
        age_days = (now - item.published_at).total_seconds() / 86400.0
        if age_days <= 2:
            score += 0.4
        elif age_days <= 7:
            score += 0.25
        elif age_days <= 30:
            score += 0.1

    if item.deadline_at is not None:
        days_left = (item.deadline_at - now).total_seconds() / 86400.0
        if days_left < 0:
            score -= 0.5
        elif days_left <= 3:
            score += 0.4
        elif days_left <= 7:
            score += 0.25
        elif days_left <= 14:
            score += 0.1

    return _clamp01(score)


def _rarity(item: OpportunityItem) -> float:
    # Heuristic: vouchers / limited time / early bird tend to be rarer.
    if item.limited_time:
        return 0.8
    if item.urgent:
        return 0.6
    return 0.4


def score_item(item: OpportunityItem, keywords_cfg: dict[str, Any], scoring_cfg: dict[str, Any]) -> OpportunityItem:
    weights = scoring_cfg.get("weights") or {}
    w_rep = float(weights.get("company_reputation", 0.30))
    w_skill = float(weights.get("skill_relevance", 0.25))
    w_benefit = float(weights.get("benefit_value", 0.25))
    w_time = float(weights.get("timeliness", 0.15))
    w_rarity = float(weights.get("rarity", 0.05))

    rep = _company_reputation(item.tags)
    skill = _skill_relevance(item, keywords_cfg)
    benefit = _benefit_value(item, keywords_cfg)
    time = _timeliness(item)
    rarity = _rarity(item)

    raw = (
        w_rep * rep
        + w_skill * skill
        + w_benefit * benefit
        + w_time * time
        + w_rarity * rarity
    )

    # Normalize to 0..100.
    score = round(_clamp01(raw) * 100.0, 1)
    return replace(item, score=score)
