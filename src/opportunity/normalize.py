from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dateutil import parser as date_parser


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v is not None)
    return str(value)


def canonicalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""

    parsed = urlparse(url)

    # Normalize scheme/netloc/path.
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"//+", "/", parsed.path or "/")

    # Drop common tracking query params.
    query_pairs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        lk = k.lower()
        if lk.startswith("utm_"):
            continue
        if lk in {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source"}:
            continue
        query_pairs.append((k, v))
    query = urlencode(query_pairs, doseq=True)

    # Strip fragments.
    fragment = ""

    return urlunparse((scheme, netloc, path.rstrip("/"), "", query, fragment))


def normalize_title(text: str) -> str:
    text = _to_text(text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = date_parser.parse(_to_text(value))
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class OpportunityItem:
    title: str
    summary: str
    content_url: str
    canonical_url: str
    source: str
    source_id: str
    published_at: Optional[datetime]
    deadline_at: Optional[datetime]
    tags: tuple[str, ...]

    # Enriched fields
    category: str = "program"
    urgent: bool = False
    limited_time: bool = False
    score: float = 0.0
    prep_checklist: Optional[tuple[str, ...]] = None


def normalize_raw_item(raw: dict[str, Any]) -> OpportunityItem:
    title = _to_text(raw.get("title")).strip()
    summary = _to_text(raw.get("summary")).strip()
    content_url = _to_text(raw.get("url") or raw.get("content_url")).strip()

    canonical_url = canonicalize_url(content_url)

    published_at = _parse_dt(raw.get("published") or raw.get("published_at"))
    deadline_at = _parse_dt(raw.get("deadline") or raw.get("deadline_at"))

    source = _to_text(raw.get("source")).strip()
    source_id = _to_text(raw.get("source_id") or source).strip()

    tags_raw = raw.get("tags") or []
    if isinstance(tags_raw, str):
        tags = (tags_raw,)
    elif isinstance(tags_raw, (list, tuple)):
        tags = tuple(str(t).strip() for t in tags_raw if t is not None and str(t).strip())
    else:
        tags = tuple()

    return OpportunityItem(
        title=title,
        summary=summary,
        content_url=content_url,
        canonical_url=canonical_url,
        source=source,
        source_id=source_id,
        published_at=published_at,
        deadline_at=deadline_at,
        tags=tags,
    )
