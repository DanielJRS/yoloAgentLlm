import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from services.config import config


@dataclass(frozen=True)
class Event:
    id: int
    event_time: str
    label: str
    confidence: float
    image_path: str | None


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    image_path TEXT
)
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(SCHEMA)


def save_event(label: str, confidence: float, image_path: str | None = None) -> int:
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO events (event_time, label, confidence, image_path) "
            "VALUES (?, ?, ?, ?)",
            (when, label, confidence, image_path),
        )
        return int(cursor.lastrowid)


def list_recent(limit: int = 12) -> list[Event]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, event_time, label, confidence, image_path "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [Event(**dict(row)) for row in rows]


def count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
    return int(row["c"])
