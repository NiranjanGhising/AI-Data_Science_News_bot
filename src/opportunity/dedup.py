from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import jellyfish

from .normalize import OpportunityItem, normalize_title


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _within_window(published_at: datetime | None, window_days: int) -> bool:
    if published_at is None:
        return True
    return published_at >= (_now_utc() - timedelta(days=window_days))


def _best(a: OpportunityItem, b: OpportunityItem) -> OpportunityItem:
    # Prefer earlier published_at; if missing, keep the other.
    if a.published_at and b.published_at:
        if a.published_at != b.published_at:
            return a if a.published_at < b.published_at else b
    elif a.published_at and not b.published_at:
        return a
    elif b.published_at and not a.published_at:
        return b

    # Prefer having a deadline.
    if (a.deadline_at is not None) != (b.deadline_at is not None):
        return a if a.deadline_at is not None else b

    # Prefer longer summary (often more informative).
    return a if len(a.summary or "") >= len(b.summary or "") else b


def dedup_items(items: Iterable[OpportunityItem], window_days: int = 60, jw_threshold: float = 0.88) -> list[OpportunityItem]:
    items_list = [i for i in items if i.title or i.canonical_url]

    # 1) Exact canonical URL.
    by_url: dict[str, OpportunityItem] = {}
    remainder: list[OpportunityItem] = []
    for i in items_list:
        if not _within_window(i.published_at, window_days):
            continue
        if i.canonical_url:
            existing = by_url.get(i.canonical_url)
            by_url[i.canonical_url] = i if existing is None else _best(existing, i)
        else:
            remainder.append(i)

    # 2) Exact normalized title.
    by_title: dict[str, OpportunityItem] = {}
    for i in list(by_url.values()) + remainder:
        t = normalize_title(i.title)
        if not t:
            continue
        existing = by_title.get(t)
        by_title[t] = i if existing is None else _best(existing, i)

    candidates = list(by_title.values())

    # 3) Fuzzy similarity on title+summary for remaining near-duplicates.
    out: list[OpportunityItem] = []
    fingerprints: list[str] = []
    for i in sorted(candidates, key=lambda x: (normalize_title(x.title), x.canonical_url)):
        fp = f"{normalize_title(i.title)} {normalize_title(i.summary)}".strip()
        if not fp:
            out.append(i)
            fingerprints.append("")
            continue

        duplicate_index = None
        for idx, existing_fp in enumerate(fingerprints):
            if not existing_fp:
                continue
            sim = jellyfish.jaro_winkler_similarity(fp, existing_fp)
            if sim >= jw_threshold:
                duplicate_index = idx
                break

        if duplicate_index is None:
            out.append(i)
            fingerprints.append(fp)
        else:
            out[duplicate_index] = _best(out[duplicate_index], i)

    return out
