"""
Optional SQLite persistence mirroring each successful CSV snapshot.

Stores one row per record as JSON for schema flexibility across NSE payloads.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("nse_downloader.sqlite_store")

_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _db_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _GLOBAL_LOCK:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


@dataclass(frozen=True)
class SnapshotMeta:
    dataset_id: str
    trade_date: str
    row_count: int
    csv_path: str


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            csv_path TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            UNIQUE(dataset_id, trade_date)
        );
        CREATE TABLE IF NOT EXISTS snapshot_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
            row_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_snapshot_rows_snapshot
            ON snapshot_rows(snapshot_id);
        """
    )
    conn.commit()


@contextmanager
def connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


def save_snapshot(db_path: Path, meta: SnapshotMeta, df: pd.DataFrame) -> None:
    """Replace prior snapshot for (dataset_id, trade_date) and insert rows."""
    if df.empty:
        logger.warning("SQLite skip: empty dataframe for %s", meta.dataset_id)
        return

    lock = _db_lock(db_path)
    with lock:
        with connect(db_path) as conn:
            init_schema(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM snapshots WHERE dataset_id = ? AND trade_date = ?",
                (meta.dataset_id, meta.trade_date),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("DELETE FROM snapshots WHERE id = ?", (existing[0],))
            cur.execute(
                """
                INSERT INTO snapshots (dataset_id, trade_date, row_count, csv_path, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    meta.dataset_id,
                    meta.trade_date,
                    meta.row_count,
                    meta.csv_path,
                    _utc_iso(),
                ),
            )
            sid = cur.lastrowid
            rows = [
                (sid, json.dumps(rec, default=str))
                for rec in df.replace({pd.NA: None}).to_dict(orient="records")
            ]
            cur.executemany(
                "INSERT INTO snapshot_rows (snapshot_id, row_json) VALUES (?, ?)",
                rows,
            )
            conn.commit()
            logger.info(
                "SQLite snapshot %s %s -> %s rows (db %s)",
                meta.dataset_id,
                meta.trade_date,
                meta.row_count,
                db_path,
            )


def dataframe_from_snapshot(conn: sqlite3.Connection, dataset_id: str, trade_date: str) -> pd.DataFrame:
    """Read back rows as DataFrame (integration / tests)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.row_json FROM snapshot_rows r
        JOIN snapshots s ON s.id = r.snapshot_id
        WHERE s.dataset_id = ? AND s.trade_date = ?
        """,
        (dataset_id, trade_date),
    )
    parsed: list[dict[str, Any]] = []
    for (blob,) in cur.fetchall():
        parsed.append(json.loads(blob))
    return pd.DataFrame(parsed)
