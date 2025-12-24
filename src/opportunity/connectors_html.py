from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from .http_client import PoliteHttpClient
from .logging_utils import log_event


def _robots_allows(url: str, user_agent: str = "*") -> bool:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots.txt can't be read, be conservative but not blocking.
        return True


def fetch_html(url: str, source: dict[str, Any], http: PoliteHttpClient) -> list[dict[str, Any]]:
    log_event("fetch_start", source_id=source.get("id"), parser="html", url=url)

    if not _robots_allows(url):
        log_event("robots_disallow", source_id=source.get("id"), url=url)
        return []

    resp = http.get(url, source_id=source.get("id", "html"), min_interval_seconds=float(source.get("rateLimitSeconds", 0.0)))
    soup = BeautifulSoup(resp.text, "lxml")

    params = source.get("params") or {}
    item_selector = params.get("itemSelector")
    link_selector = params.get("linkSelector")

    items: list[dict[str, Any]] = []

    if item_selector and link_selector:
        for node in soup.select(item_selector)[:50]:
            a = node.select_one(link_selector)
            if not a:
                continue
            href = a.get("href") or ""
            title = (a.get_text(" ", strip=True) or "").strip()
            if not href or not title:
                continue
            items.append(
                {
                    "title": title,
                    "summary": node.get_text(" ", strip=True),
                    "url": urljoin(url, href),
                    "published": "",
                    "source": source.get("name"),
                    "source_id": source.get("id"),
                    "tags": source.get("tags", []),
                    "raw": {"href": href},
                }
            )
    else:
        # Fallback: treat the page as a single announcement.
        title = (soup.title.get_text(strip=True) if soup.title else "").strip()
        if title:
            items.append(
                {
                    "title": title,
                    "summary": "",
                    "url": url,
                    "published": "",
                    "source": source.get("name"),
                    "source_id": source.get("id"),
                    "tags": source.get("tags", []),
                    "raw": {},
                }
            )

    log_event("fetch_done", source_id=source.get("id"), count=len(items))
    return items
