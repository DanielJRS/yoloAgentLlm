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


def _int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    return int(raw) if raw else default


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
    )


config = load_config()
