"""SQLite metadata, passage and job storage (FTS5 for passage search)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_files (
  content_hash TEXT PRIMARY KEY,
  rel_path TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  media_type TEXT,
  first_retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fetch_attempts (
  attempt_id TEXT PRIMARY KEY,
  source_kind TEXT NOT NULL,
  url TEXT NOT NULL,
  final_url TEXT,
  state TEXT NOT NULL,
  http_status INTEGER,
  content_type TEXT,
  bytes INTEGER,
  content_hash TEXT,
  error TEXT,
  company_id TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS security_master (
  symbol TEXT NOT NULL,
  legal_name TEXT NOT NULL,
  series TEXT,
  listing_date TEXT,
  isin TEXT,
  source_url TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  PRIMARY KEY (symbol, source_hash)
);
CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL UNIQUE,
  legal_name TEXT NOT NULL,
  exchange TEXT NOT NULL,
  isin TEXT NOT NULL,
  series TEXT NOT NULL,
  listing_date TEXT,
  identity_source_url TEXT NOT NULL,
  identity_source_hash TEXT NOT NULL,
  resolved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS announcements (
  announcement_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  source_key TEXT NOT NULL UNIQUE,
  category TEXT,
  subject TEXT,
  published_at TEXT,
  published_at_raw TEXT,
  attachment_url TEXT,
  attachment_version_id TEXT,
  attachment_state TEXT,
  retrieved_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_hash TEXT,
  raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_versions (
  version_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  period_label TEXT,
  period_start TEXT,
  period_end TEXT,
  event_date TEXT,
  source_url TEXT NOT NULL,
  final_url TEXT,
  host TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  media_type TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  page_count INTEGER,
  published_at TEXT,
  published_precision TEXT,
  availability_status TEXT NOT NULL,
  availability_evidence TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  parse_status TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  identification TEXT NOT NULL,
  UNIQUE (document_id, content_hash)
);
CREATE TABLE IF NOT EXISTS passages (
  passage_id TEXT PRIMARY KEY,
  version_id TEXT NOT NULL,
  page_index INTEGER NOT NULL,
  printed_page TEXT,
  speaker TEXT,
  text TEXT NOT NULL,
  extraction_status TEXT NOT NULL,
  seq INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS passages_version ON passages(version_id, page_index, seq);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
  passage_id UNINDEXED, version_id UNINDEXED, text, tokenize = 'porter unicode61'
);
CREATE TABLE IF NOT EXISTS market_observations (
  symbol TEXT NOT NULL,
  series TEXT NOT NULL,
  isin TEXT,
  trading_date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, prev_close REAL,
  volume INTEGER,
  source_url TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  PRIMARY KEY (symbol, series, trading_date, source_hash)
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  state TEXT NOT NULL,
  stage TEXT,
  stages TEXT NOT NULL,
  request TEXT NOT NULL,
  result TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_key ON jobs(idempotency_key);
CREATE TABLE IF NOT EXISTS model_calls (
  call_id TEXT PRIMARY KEY,
  job_id TEXT,
  model TEXT NOT NULL,
  reserved_usd REAL NOT NULL,
  actual_usd REAL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS derived_cache (
  cache_key TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Store:
    """Thin SQLite wrapper. One connection per operation; writes serialised by a lock."""

    def __init__(self, db_path: Path, files_dir: Path):
        self.db_path = Path(db_path)
        self.files_dir = Path(files_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ---------- raw files (immutable, content addressed) ----------
    def put_file(self, data: bytes, media_type: str, suffix: str) -> str:
        digest = sha256_bytes(data)
        rel = Path(digest[:2]) / f"{digest}{suffix}"
        path = self.files_dir / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO raw_files VALUES (?,?,?,?,?)",
                (digest, str(rel), len(data), media_type, utcnow()),
            )
        return digest

    def file_path(self, content_hash: str) -> Optional[Path]:
        with self.connect() as conn:
            row = conn.execute("SELECT rel_path FROM raw_files WHERE content_hash=?", (content_hash,)).fetchone()
        if not row:
            return None
        path = self.files_dir / row["rel_path"]
        return path if path.exists() else None

    # ---------- generic helpers ----------
    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)

    def insert(self, table: str, row: Dict[str, Any], mode: str = "INSERT") -> None:
        cols = list(row.keys())
        values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
        sql = f"{mode} INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
        with self.connect() as conn:
            conn.execute(sql, values)
