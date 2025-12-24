-- Opportunity Radar SQLite init

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
);

CREATE TABLE IF NOT EXISTS scan_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scanned_at TEXT,
  raw_count INTEGER,
  dedup_count INTEGER,
  fresh_count INTEGER
);
