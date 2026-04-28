from datetime import datetime

import cv2

from services.config import config


def save_capture(frame) -> str:
    config.captures_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"capture_{ts}.jpg"
    path = config.captures_dir / filename
    cv2.imwrite(str(path), frame)
    return f"/static/captures/{filename}"
