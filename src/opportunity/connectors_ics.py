from __future__ import annotations

from typing import Any

from icalendar import Calendar

from .http_client import PoliteHttpClient
from .logging_utils import log_event


def fetch_ics(url: str, source: dict[str, Any], http: PoliteHttpClient) -> list[dict[str, Any]]:
    log_event("fetch_start", source_id=source.get("id"), parser="ics", url=url)
    resp = http.get(url, source_id=source.get("id", "ics"), min_interval_seconds=float(source.get("rateLimitSeconds", 0.0)))
    cal = Calendar.from_ical(resp.content)

    items: list[dict[str, Any]] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        title = str(component.get("summary") or "").strip()
        desc = str(component.get("description") or "").strip()
        link = str(component.get("url") or component.get("location") or url)

        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        published = None
        deadline = None

        if dtstart is not None:
            try:
                published = dtstart.dt
            except Exception:
                published = None

        if dtend is not None:
            try:
                deadline = dtend.dt
            except Exception:
                deadline = None

        items.append(
            {
                "title": title,
                "summary": desc,
                "url": link,
                "published": published,
                "deadline": deadline,
                "source": source.get("name"),
                "source_id": source.get("id"),
                "tags": source.get("tags", []),
                "raw": {"summary": title},
            }
        )

    log_event("fetch_done", source_id=source.get("id"), count=len(items))
    return items
