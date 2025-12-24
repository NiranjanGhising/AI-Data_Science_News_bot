from __future__ import annotations

from typing import Any

import feedparser

from .logging_utils import log_event


def fetch_rss(url: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    log_event("fetch_start", source_id=source.get("id"), parser="rss", url=url)
    feed = feedparser.parse(url)
    items: list[dict[str, Any]] = []
    for e in getattr(feed, "entries", [])[:50]:
        items.append(
            {
                "title": getattr(e, "title", ""),
                "summary": getattr(e, "summary", "") or getattr(e, "description", ""),
                "url": getattr(e, "link", ""),
                "published": getattr(e, "published", getattr(e, "updated", "")),
                "source": source.get("name"),
                "source_id": source.get("id"),
                "tags": source.get("tags", []),
                "raw": e,
            }
        )
    log_event("fetch_done", source_id=source.get("id"), count=len(items))
    return items
