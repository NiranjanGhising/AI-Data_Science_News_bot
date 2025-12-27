from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True)
class LinkSummary:
    summary: str
    why_read: str
    extracted_title: str
    fetched_at_iso: str
    error: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_meta(soup: BeautifulSoup, *, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return _norm_ws(tag.get("content"))
    return ""


def _extract_og(soup: BeautifulSoup, *, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return _norm_ws(tag.get("content"))
    return ""


def _extract_title(soup: BeautifulSoup) -> str:
    t = _extract_og(soup, prop="og:title")
    if t:
        return t
    if soup.title and soup.title.get_text():
        return _norm_ws(soup.title.get_text())
    h1 = soup.find("h1")
    if h1 and h1.get_text():
        return _norm_ws(h1.get_text())
    return ""


def _strip_unhelpful_tags(soup: BeautifulSoup) -> None:
    for tag_name in [
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
    ]:
        for t in soup.find_all(tag_name):
            t.decompose()


def _extract_main_text(html: str, *, max_chars: int) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")
    _strip_unhelpful_tags(soup)

    title = _extract_title(soup)
    desc = _extract_og(soup, prop="og:description") or _extract_meta(soup, name="description")

    body = soup.body or soup
    text = _norm_ws(body.get_text(" "))

    if max_chars and len(text) > max_chars:
        text = text[:max_chars]

    return text, title, desc


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\(\[])", re.M)


def _sentences(text: str) -> list[str]:
    text = _norm_ws(text)
    if not text:
        return []

    parts = _SENT_SPLIT.split(text)
    out: list[str] = []
    for p in parts:
        p = _norm_ws(p)
        if len(p) < 40:
            continue
        if len(p) > 360:
            p = p[:357].rstrip() + "..."
        out.append(p)
    return out


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{1,}")


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def summarize_extractive(text: str, *, max_sentences: int = 2) -> str:
    sents = _sentences(text)
    if not sents:
        return ""

    # Build word frequency over the whole text (lightweight TF scoring)
    freq: dict[str, int] = {}
    for w in _words(text):
        if w in _STOPWORDS:
            continue
        if len(w) <= 2:
            continue
        freq[w] = freq.get(w, 0) + 1

    if not freq:
        return " ".join(sents[:max_sentences])

    def score_sentence(s: str) -> float:
        ws = _words(s)
        if not ws:
            return 0.0
        total = 0
        for w in ws:
            if w in _STOPWORDS or len(w) <= 2:
                continue
            total += freq.get(w, 0)
        return total / max(1, len(ws))

    ranked = sorted([(i, score_sentence(s), s) for i, s in enumerate(sents)], key=lambda x: x[1], reverse=True)
    top = sorted(ranked[: max_sentences], key=lambda x: x[0])
    return " ".join(s for _, _, s in top).strip()


def _keyword_hits(*, text: str, keywords: Iterable[str]) -> list[str]:
    t = (text or "").lower()
    hits = []
    for k in keywords or []:
        kk = (k or "").strip().lower()
        if not kk:
            continue
        if kk in t:
            hits.append(k)
    # Dedup + cap
    uniq = []
    seen = set()
    for h in hits:
        if h.lower() in seen:
            continue
        seen.add(h.lower())
        uniq.append(h)
    return uniq[:3]


def _build_why_read(
    *,
    summary: str,
    desc: str,
    source: str = "",
    score: Optional[int] = None,
    keywords: Optional[list[str]] = None,
) -> str:
    signals: list[str] = []

    combined = f"{desc} {summary}".strip()

    if keywords:
        hits = _keyword_hits(text=combined, keywords=keywords)
        if hits:
            signals.append("Matches: " + ", ".join(hits))

    lc = combined.lower()
    if any(x in lc for x in ["release", "changelog", "release notes", "breaking change", "migration"]):
        signals.append("Likely includes an actionable update")
    elif any(x in lc for x in ["benchmark", "eval", "leaderboard", "swe-bench"]):
        signals.append("Useful for comparing approaches")
    elif any(x in lc for x in ["api", "sdk", "library", "tool", "agent"]):
        signals.append("Practical for building")

    if score is not None and score >= 6:
        signals.append(f"High relevance (score {score})")

    if source:
        signals.append(source)

    # Keep it short
    out = "; ".join(signals[:3]).strip()
    return out


def summarize_link(
    url: str,
    *,
    title_hint: str = "",
    source: str = "",
    score: Optional[int] = None,
    keywords: Optional[list[str]] = None,
    timeout_s: int = 20,
    max_bytes: int = 900_000,
    max_chars: int = 8000,
) -> LinkSummary:
    url = (url or "").strip()
    if not url:
        return LinkSummary(summary="", why_read="", extracted_title=title_hint or "", fetched_at_iso=_now_iso(), error="missing_url")

    if os.getenv("RR_SUMMARIZE_LINKS", "1") != "1":
        return LinkSummary(summary="", why_read="", extracted_title=title_hint or "", fetched_at_iso=_now_iso(), error="disabled")

    headers = {
        "User-Agent": os.getenv("RR_USER_AGENT", _DEFAULT_UA),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    }

    started = time.time()
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_s, stream=True)
        resp.raise_for_status()

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "application/pdf" in ctype:
            return LinkSummary(
                summary="(PDF link — open to skim abstract/intro)",
                why_read=_build_why_read(summary="pdf", desc="", source=source, score=score, keywords=keywords) or source,
                extracted_title=title_hint or "",
                fetched_at_iso=_now_iso(),
                error="pdf",
            )

        # Read up to max_bytes
        raw = b""
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            raw += chunk
            if len(raw) >= max_bytes:
                break

        # requests will guess encoding; fall back to utf-8
        enc = resp.encoding or "utf-8"
        html = raw.decode(enc, errors="replace")

        text, extracted_title, desc = _extract_main_text(html, max_chars=max_chars)
        summary = summarize_extractive(desc or text, max_sentences=2)
        summary = summary or summarize_extractive(text, max_sentences=2)

        extracted_title = extracted_title or title_hint or ""
        why = _build_why_read(summary=summary, desc=desc, source=source, score=score, keywords=keywords) or ""

        # Hard caps to keep Telegram messages sane
        summary = _norm_ws(summary)[:320]
        why = _norm_ws(why)[:220]

        elapsed_ms = int((time.time() - started) * 1000)
        _ = elapsed_ms  # reserved for future logging

        return LinkSummary(summary=summary, why_read=why, extracted_title=extracted_title, fetched_at_iso=_now_iso())

    except Exception as e:
        return LinkSummary(
            summary="",
            why_read=source or "",
            extracted_title=title_hint or "",
            fetched_at_iso=_now_iso(),
            error=f"fetch_failed: {type(e).__name__}",
        )
