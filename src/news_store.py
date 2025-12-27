from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def canonicalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = (parsed.path or "/").rstrip("/")

    query_pairs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        lk = k.lower()
        if lk.startswith("utm_"):
            continue
        if lk in {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source"}:
            continue
        query_pairs.append((k, v))
    query = urlencode(query_pairs, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


class NewsStore:
    """Tracks AI/Research items that were sent so we don't repeat endlessly.

    Policy:
      - Non-important items: send once.
      - Important items: can be re-sent up to `max_important_reposts` times total.
      - Reposts require at least `min_repost_interval_hours` since last notify.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_items (
                    item_key TEXT PRIMARY KEY,
                    canonical_url TEXT,
                    title TEXT,
                    source TEXT,
                    url TEXT,
                    published_at TEXT,
                    score INTEGER,
                    important INTEGER,
                    first_seen_at TEXT,
                    last_seen_at TEXT,
                    notify_count INTEGER,
                    last_notified_at TEXT,
                    link_summary TEXT,
                    why_read TEXT,
                    summary_fetched_at TEXT
                )
                """
            )

            # Backwards-compatible schema upgrades for existing DBs.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_items)").fetchall()}
            if "link_summary" not in cols:
                conn.execute("ALTER TABLE ai_items ADD COLUMN link_summary TEXT")
            if "why_read" not in cols:
                conn.execute("ALTER TABLE ai_items ADD COLUMN why_read TEXT")
            if "summary_fetched_at" not in cols:
                conn.execute("ALTER TABLE ai_items ADD COLUMN summary_fetched_at TEXT")

    @staticmethod
    def make_item_key(item: dict) -> str:
        doi = (item.get("DOI") or item.get("doi") or "").strip()
        if doi:
            return f"doi:{doi.lower()}"
        arxiv = (item.get("arxiv_id") or item.get("arxiv") or "").strip()
        if arxiv:
            return f"arxiv:{arxiv}"
        url = item.get("url") or item.get("URL") or item.get("link") or ""
        canon = canonicalize_url(url)
        return f"url:{canon}" if canon else ""

    def upsert(self, *, item_key: str, canonical_url: str, title: str, source: str, url: str,
               published_at: Optional[str], score: int, important: bool) -> None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT item_key, first_seen_at, notify_count, last_notified_at FROM ai_items WHERE item_key = ?",
                (item_key,),
            ).fetchone()

            first_seen = row["first_seen_at"] if row else _now_iso()
            notify_count = int(row["notify_count"]) if row and row["notify_count"] is not None else 0
            last_notified_at = row["last_notified_at"] if row else None

            conn.execute(
                """
                INSERT INTO ai_items (
                    item_key, canonical_url, title, source, url, published_at, score, important,
                    first_seen_at, last_seen_at, notify_count, last_notified_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(item_key) DO UPDATE SET
                    canonical_url=excluded.canonical_url,
                    title=excluded.title,
                    source=excluded.source,
                    url=excluded.url,
                    published_at=excluded.published_at,
                    score=excluded.score,
                    important=excluded.important,
                    last_seen_at=excluded.last_seen_at,
                    first_seen_at=excluded.first_seen_at,
                    notify_count=excluded.notify_count,
                    last_notified_at=excluded.last_notified_at
                """,
                (
                    item_key,
                    canonical_url,
                    title,
                    source,
                    url,
                    published_at,
                    int(score),
                    1 if important else 0,
                    first_seen,
                    _now_iso(),
                    notify_count,
                    last_notified_at,
                ),
            )

    def select_to_send(
        self,
        *,
        limit: int,
        max_important_reposts: int = 3,
        min_repost_interval_hours: int = 20,
        require_important: bool = False,
    ) -> list[sqlite3.Row]:
        min_time = (_now_utc() - timedelta(hours=min_repost_interval_hours)).isoformat()

        where = []
        params: list[object] = []
        if require_important:
            where.append("important = 1")

        # eligible if never notified OR important and under cap and interval passed
        where.append(
            "(notify_count = 0 OR (important = 1 AND notify_count < ? AND (last_notified_at IS NULL OR last_notified_at < ?)))"
        )
        params.extend([max_important_reposts, min_time])

        where_sql = " AND ".join(where)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM ai_items
                WHERE {where_sql}
                ORDER BY score DESC, published_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return rows

    def mark_notified(self, item_keys: Iterable[str]) -> None:
        with self._conn() as conn:
            for k in item_keys:
                conn.execute(
                    """
                    UPDATE ai_items
                    SET notify_count = COALESCE(notify_count, 0) + 1,
                        last_notified_at = ?
                    WHERE item_key = ?
                    """,
                    (_now_iso(), k),
                )

    def get_summary(self, *, item_key: str) -> tuple[str, str, Optional[str]]:
        """Returns (summary, why_read, fetched_at_iso)."""
        if not item_key:
            return "", "", None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT link_summary, why_read, summary_fetched_at FROM ai_items WHERE item_key = ?",
                (item_key,),
            ).fetchone()
        if not row:
            return "", "", None
        return (row["link_summary"] or ""), (row["why_read"] or ""), (row["summary_fetched_at"] or None)

    def upsert_summary(self, *, item_key: str, link_summary: str, why_read: str, fetched_at_iso: Optional[str]) -> None:
        if not item_key:
            return
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE ai_items
                SET link_summary = ?, why_read = ?, summary_fetched_at = ?
                WHERE item_key = ?
                """,
                (link_summary or "", why_read or "", fetched_at_iso or _now_iso(), item_key),
            )
