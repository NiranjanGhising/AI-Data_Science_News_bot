from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable, Optional

from .normalize import OpportunityItem


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt_to_iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


class OpportunityStore:
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
                CREATE TABLE IF NOT EXISTS items (
                    canonical_url TEXT PRIMARY KEY,
                    title TEXT,
                    title_norm TEXT,
                    summary TEXT,
                    summary_norm TEXT,
                    content_url TEXT,
                    source TEXT,
                    source_id TEXT,
                    published_at TEXT,
                    deadline_at TEXT,
                    category TEXT,
                    score REAL,
                    urgent INTEGER,
                    limited_time INTEGER,
                    tags_json TEXT,
                    prep_json TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT,
                    notified_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scanned_at TEXT,
                    raw_count INTEGER,
                    dedup_count INTEGER,
                    fresh_count INTEGER
                )
                """
            )

    def upsert_items(self, items: Iterable[OpportunityItem]) -> None:
        with self._conn() as conn:
            for i in items:
                if not i.canonical_url:
                    continue

                row = conn.execute(
                    "SELECT canonical_url, first_seen_at, notified_at FROM items WHERE canonical_url = ?",
                    (i.canonical_url,),
                ).fetchone()

                first_seen_at = row["first_seen_at"] if row else _now_iso()
                notified_at = row["notified_at"] if row else None

                conn.execute(
                    """
                    INSERT INTO items (
                        canonical_url, title, title_norm, summary, summary_norm, content_url,
                        source, source_id, published_at, deadline_at, category, score,
                        urgent, limited_time, tags_json, prep_json,
                        first_seen_at, last_seen_at, notified_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(canonical_url) DO UPDATE SET
                        title=excluded.title,
                        title_norm=excluded.title_norm,
                        summary=excluded.summary,
                        summary_norm=excluded.summary_norm,
                        content_url=excluded.content_url,
                        source=excluded.source,
                        source_id=excluded.source_id,
                        published_at=excluded.published_at,
                        deadline_at=excluded.deadline_at,
                        category=excluded.category,
                        score=excluded.score,
                        urgent=excluded.urgent,
                        limited_time=excluded.limited_time,
                        tags_json=excluded.tags_json,
                        prep_json=excluded.prep_json,
                        last_seen_at=excluded.last_seen_at,
                        first_seen_at=excluded.first_seen_at,
                        notified_at=excluded.notified_at
                    """,
                    (
                        i.canonical_url,
                        i.title,
                        i.title.casefold().strip(),
                        i.summary,
                        i.summary.casefold().strip(),
                        i.content_url,
                        i.source,
                        i.source_id,
                        _dt_to_iso(i.published_at),
                        _dt_to_iso(i.deadline_at),
                        i.category,
                        float(i.score),
                        1 if i.urgent else 0,
                        1 if i.limited_time else 0,
                        json.dumps(list(i.tags), ensure_ascii=False),
                        json.dumps(list(i.prep_checklist) if i.prep_checklist else None, ensure_ascii=False),
                        first_seen_at,
                        _now_iso(),
                        notified_at,
                    ),
                )

    def get_unnotified_items(self, limit: int = 1000) -> list[OpportunityItem]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM items
                WHERE notified_at IS NULL
                ORDER BY score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_item(r) for r in rows]

    def get_unnotified_urgent(self, limit: int = 50) -> list[OpportunityItem]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM items
                WHERE notified_at IS NULL AND urgent = 1
                ORDER BY score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def mark_notified(self, canonical_urls: Iterable[str]) -> None:
        with self._conn() as conn:
            for u in canonical_urls:
                conn.execute(
                    "UPDATE items SET notified_at = ? WHERE canonical_url = ?",
                    (_now_iso(), u),
                )

    def _row_to_item(self, r: sqlite3.Row) -> OpportunityItem:
        tags = tuple(json.loads(r["tags_json"]) or []) if r["tags_json"] else tuple()
        prep = None
        if r["prep_json"]:
            try:
                v = json.loads(r["prep_json"])
                if isinstance(v, list):
                    prep = tuple(str(x) for x in v)
            except Exception:
                prep = None

        item = OpportunityItem(
            title=r["title"] or "",
            summary=r["summary"] or "",
            content_url=r["content_url"] or "",
            canonical_url=r["canonical_url"] or "",
            source=r["source"] or "",
            source_id=r["source_id"] or "",
            published_at=_iso_to_dt(r["published_at"]),
            deadline_at=_iso_to_dt(r["deadline_at"]),
            tags=tags,
            category=r["category"] or "program",
            urgent=bool(r["urgent"]),
            limited_time=bool(r["limited_time"]),
            score=float(r["score"] or 0.0),
            prep_checklist=prep,
        )
        return item
