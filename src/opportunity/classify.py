from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .normalize import OpportunityItem


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _text(item: OpportunityItem) -> str:
    return f"{item.title} {item.summary}".lower()


def classify_item(item: OpportunityItem, keywords_cfg: dict[str, Any], urgent_threshold_days: int = 7) -> OpportunityItem:
    text = _text(item)

    category = "program"
    cat_kw: dict[str, list[str]] = (keywords_cfg.get("category_keywords") or {})
    for cat, kws in cat_kw.items():
        if not isinstance(kws, list):
            continue
        if any(str(k).lower() in text for k in kws):
            category = str(cat)
            break

    urgency_keywords = [str(k).lower() for k in (keywords_cfg.get("urgency_keywords") or [])]
    limited_keywords = [str(k).lower() for k in (keywords_cfg.get("limited_time_keywords") or [])]

    keyword_urgent = any(k in text for k in urgency_keywords)
    limited_time = any(k in text for k in limited_keywords)

    deadline_urgent = False
    if item.deadline_at is not None:
        deadline_urgent = item.deadline_at <= (_now_utc() + timedelta(days=urgent_threshold_days))

    urgent = bool(deadline_urgent or keyword_urgent)

    # Recurrence prep guidance (currently only GSoC rules in config).
    prep = None
    recurrence = keywords_cfg.get("recurrence") or {}
    if isinstance(recurrence, dict):
        for _, rule in recurrence.items():
            if not isinstance(rule, dict):
                continue
            triggers = [str(t).lower() for t in (rule.get("triggers") or [])]
            if triggers and any(t in text for t in triggers):
                checklist = rule.get("prep_checklist") or []
                if isinstance(checklist, list) and checklist:
                    prep = tuple(str(x) for x in checklist)
                break

    return OpportunityItem(
        **{**item.__dict__, "category": category, "urgent": urgent, "limited_time": bool(limited_time), "prep_checklist": prep}
    )
