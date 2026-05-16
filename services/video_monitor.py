import logging
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import cv2
from ultralytics import YOLO

from services.capture_store import save_capture
from services.config import config
from services.event_repository import save_event

logger = logging.getLogger("uvicorn.error")

EVENT_COOLDOWN_SECONDS = 3.0
MIN_CONFIDENCE = 0.5


class VideoMonitor:
    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._model: YOLO | None = None
        self._latest_jpeg: bytes | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._frames_read = 0
        self._events_saved = 0
        self._last_event_time: dict[str, float] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        config.captures_dir.mkdir(parents=True, exist_ok=True)
        config.models_dir.mkdir(parents=True, exist_ok=True)
        model_path = config.models_dir / "yolov8n.pt"
        self._model = YOLO(str(model_path) if model_path.exists() else "yolov8n.pt")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="video-monitor")
        self._thread.start()
        logger.info("VideoMonitor started: source=%s", _safe_source_display(config.camera_source))

    def stop(self) -> None:
        self._stop_event.set()
        cap = self._cap
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
            self._cap = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        logger.info("VideoMonitor stopped")

    def status(self) -> dict:
        return {
            "online": self._connected,
            "connected": self._connected,
            "has_live_frame": self._latest_jpeg is not None,
            "source_type": _source_type(config.camera_source),
            "frames_read": self._frames_read,
            "events_saved": self._events_saved,
        }

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def _open(self) -> bool:
        source: int | str = config.camera_source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            cap.release()
            self._connected = False
            return False
        self._cap = cap
        self._connected = True
        return True

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None or not self._connected:
                if not self._open():
                    logger.warning("camera open failed; retry in %ss", config.camera_reconnect_seconds)
                    self._stop_event.wait(config.camera_reconnect_seconds)
                    continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                logger.warning("frame read failed; reconnecting")
                self._cap.release()
                self._cap = None
                self._connected = False
                self._stop_event.wait(config.camera_reconnect_seconds)
                continue

            self._frames_read += 1
            self._process_frame(frame)

    def _process_frame(self, frame) -> None:
        ok, buf = cv2.imencode(".jpg", frame)
        if ok:
            with self._lock:
                self._latest_jpeg = buf.tobytes()

        try:
            results = self._model.predict(frame, verbose=False, imgsz=640)
        except Exception:
            logger.exception("YOLO inference failed")
            return

        target = set(config.target_classes)
        names = self._model.names
        now = time.monotonic()
        capture_path: str | None = None

        for r in results:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue
            for cls_idx, conf in zip(boxes.cls.tolist(), boxes.conf.tolist()):
                label = names.get(int(cls_idx))
                if label not in target or conf < MIN_CONFIDENCE:
                    continue
                last = self._last_event_time.get(label, 0.0)
                if now - last < EVENT_COOLDOWN_SECONDS:
                    continue
                if capture_path is None:
                    capture_path = save_capture(frame)
                save_event(label, float(conf), capture_path)
                self._last_event_time[label] = now
                self._events_saved += 1


def _source_type(source: str) -> str:
    if source.isdigit():
        return "webcam"
    if source.startswith(("http://", "https://", "rtsp://")):
        return "stream"
    return "file"


def _short(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[:n] + "..."


def _safe_source_display(source: str) -> str:
    if "://" not in source:
        return _short(source)
    parts = urlsplit(source)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    if parts.username or parts.password:
        host = f"***:***@{host}"
    return _short(urlunsplit((parts.scheme, host, parts.path, "", "")))


monitor = VideoMonitor()
