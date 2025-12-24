from __future__ import annotations

import json
from typing import Any

from .http_client import PoliteHttpClient
from .logging_utils import log_event


def _dig(obj: Any, path: str) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def fetch_json(url: str, source: dict[str, Any], http: PoliteHttpClient) -> list[dict[str, Any]]:
    """Fetches a JSON API and maps it into a list of raw items.

    Optional mapping via source['params']:
      - itemsPath: dot path to list
      - titleField/urlField/summaryField/publishedField/deadlineField: field names
    """
    params = source.get("params") or {}
    log_event("fetch_start", source_id=source.get("id"), parser="json", url=url)

    resp = http.get(url, source_id=source.get("id", "json"), min_interval_seconds=float(source.get("rateLimitSeconds", 0.0)))
    data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)

    items = _dig(data, str(params.get("itemsPath") or ""))
    if not isinstance(items, list):
        # best-effort: common patterns
        for candidate in ("items", "results", "data"):
            if isinstance(data, dict) and isinstance(data.get(candidate), list):
                items = data.get(candidate)
                break

    if not isinstance(items, list):
        items = []

    title_f = params.get("titleField") or "title"
    url_f = params.get("urlField") or "url"
    summary_f = params.get("summaryField") or "summary"
    published_f = params.get("publishedField") or "published"
    deadline_f = params.get("deadlineField") or "deadline"

    out: list[dict[str, Any]] = []
    for it in items[:100]:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "title": it.get(title_f, ""),
                "summary": it.get(summary_f, ""),
                "url": it.get(url_f, "") or url,
                "published": it.get(published_f, ""),
                "deadline": it.get(deadline_f),
                "source": source.get("name"),
                "source_id": source.get("id"),
                "tags": source.get("tags", []),
                "raw": it,
            }
        )

    log_event("fetch_done", source_id=source.get("id"), count=len(out))
    return out
