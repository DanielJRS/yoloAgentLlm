import sqlite3
from contextlib import contextmanager
from typing import Iterator

from services.config import config
from services.schemas import WeatherSnapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS tb_weather_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    temperature_c REAL NOT NULL,
    humidity_percent INTEGER NOT NULL,
    wind_speed_kmh REAL NOT NULL,
    condition TEXT NOT NULL,
    source TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
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


def init_weather_db() -> None:
    with _connect() as conn:
        conn.execute(SCHEMA)


def save_weather_snapshot(snapshot: WeatherSnapshot) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tb_weather_snapshot ("
            "collected_at, observed_at, temperature_c, humidity_percent, "
            "wind_speed_kmh, condition, source, latitude, longitude"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.collected_at,
                snapshot.observed_at,
                snapshot.temperature_c,
                snapshot.humidity_percent,
                snapshot.wind_speed_kmh,
                snapshot.condition,
                snapshot.source,
                snapshot.latitude,
                snapshot.longitude,
            ),
        )
        return int(cursor.lastrowid)


def get_latest_weather_snapshot() -> WeatherSnapshot | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT collected_at, observed_at, temperature_c, humidity_percent, "
            "wind_speed_kmh, condition, source, latitude, longitude "
            "FROM tb_weather_snapshot ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return WeatherSnapshot(**dict(row)) if row else None

