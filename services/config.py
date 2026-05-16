from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Config:
    ollama_url: str
    ollama_model: str
    ollama_timeout: int
    ollama_keep_alive: str
    agent_event_limit: int
    camera_source: str
    camera_reconnect_seconds: int
    target_classes: tuple[str, ...]
    base_dir: Path
    captures_dir: Path
    models_dir: Path
    database_path: Path
    cors_origins: tuple[str, ...]
    weather_latitude: float | None
    weather_longitude: float | None
    weather_ttl_minutes: int
    weather_user_agent: str | None
    weather_max_calls_per_hour: int


def _int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    return int(raw) if raw else default


def _float(name: str) -> float | None:
    raw = (os.getenv(name) or "").strip()
    return float(raw) if raw else None


def _csv(name: str) -> tuple[str, ...]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_config() -> Config:
    return Config(
        ollama_url=os.getenv("OLLAMA_URL") or "http://127.0.0.1:11434/api/chat",
        ollama_model=os.getenv("OLLAMA_MODEL") or "llama3",
        ollama_timeout=_int("OLLAMA_TIMEOUT", 120),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE") or "30m",
        agent_event_limit=_int("AGENT_EVENT_LIMIT", 12),
        camera_source=os.getenv("CAMERA_SOURCE") or "0",
        camera_reconnect_seconds=_int("CAMERA_RECONNECT_SECONDS", 5),
        target_classes=("person", "car", "truck", "bus", "motorcycle"),
        base_dir=BASE_DIR,
        captures_dir=BASE_DIR / "static" / "captures",
        models_dir=BASE_DIR / "models",
        database_path=BASE_DIR / "detections.db",
        cors_origins=_csv("CORS_ORIGINS"),
        weather_latitude=_float("WEATHER_LATITUDE"),
        weather_longitude=_float("WEATHER_LONGITUDE"),
        weather_ttl_minutes=_int("WEATHER_TTL_MINUTES", 30),
        weather_user_agent=(os.getenv("WEATHER_USER_AGENT") or "").strip() or None,
        weather_max_calls_per_hour=_int("WEATHER_MAX_CALLS_PER_HOUR", 2),
    )


config = load_config()
