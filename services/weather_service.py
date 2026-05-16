import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from services.config import config
from services.external_data_client import ExternalDataError, external_data_client
from services.schemas import WeatherSnapshot
from services.weather_repository import get_latest_weather_snapshot, save_weather_snapshot

logger = logging.getLogger("uvicorn.error")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_NAME = "Open-Meteo"

WEATHER_CODES = {
    0: "ceu limpo",
    1: "principalmente limpo",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina com geada",
    51: "garoa fraca",
    53: "garoa moderada",
    55: "garoa intensa",
    61: "chuva fraca",
    63: "chuva moderada",
    65: "chuva forte",
    80: "pancadas fracas",
    81: "pancadas moderadas",
    82: "pancadas fortes",
    95: "trovoadas",
}


class WeatherUnavailable(RuntimeError):
    pass


class WeatherService:
    def __init__(self) -> None:
        self._cached: WeatherSnapshot | None = None
        self._expires_at = 0.0
        self._calls: deque[float] = deque()

    def latest_cached(self) -> WeatherSnapshot | None:
        if self._cached is not None:
            return self._cached
        self._cached = get_latest_weather_snapshot()
        return self._cached

    async def get_snapshot(self, *, force_refresh: bool = False) -> WeatherSnapshot:
        now = time.monotonic()
        if not force_refresh and self._cached is not None and now < self._expires_at:
            return self._cached

        self._drop_old_calls(now)
        if len(self._calls) >= config.weather_max_calls_per_hour:
            fallback = self.latest_cached()
            if fallback is not None:
                return fallback
            raise WeatherUnavailable("limite horario de chamadas externas atingido")

        try:
            snapshot = await self._fetch_current_weather()
        except (ExternalDataError, WeatherUnavailable) as exc:
            logger.warning("weather refresh failed: %s", exc)
            fallback = self.latest_cached()
            if fallback is not None:
                return fallback
            raise WeatherUnavailable(str(exc)) from exc

        self._calls.append(now)
        self._cached = snapshot
        self._expires_at = now + (config.weather_ttl_minutes * 60)
        save_weather_snapshot(snapshot)
        return snapshot

    async def _fetch_current_weather(self) -> WeatherSnapshot:
        if config.weather_latitude is None or config.weather_longitude is None:
            raise WeatherUnavailable("WEATHER_LATITUDE/WEATHER_LONGITUDE nao configurados")
        if not config.weather_user_agent:
            raise WeatherUnavailable("WEATHER_USER_AGENT nao configurado")

        data = await external_data_client.get_json(
            OPEN_METEO_URL,
            params={
                "latitude": config.weather_latitude,
                "longitude": config.weather_longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            },
            headers={"User-Agent": config.weather_user_agent},
            timeout=8.0,
        )
        return self._parse_open_meteo(data)

    def _parse_open_meteo(self, data: dict[str, Any]) -> WeatherSnapshot:
        current = data.get("current")
        if not isinstance(current, dict):
            raise WeatherUnavailable("campo current ausente na resposta de clima")

        code = int(current.get("weather_code", -1))
        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return WeatherSnapshot(
            temperature_c=float(current["temperature_2m"]),
            humidity_percent=int(current["relative_humidity_2m"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            condition=WEATHER_CODES.get(code, f"codigo meteorologico {code}"),
            observed_at=str(current["time"]),
            collected_at=collected_at,
            source=SOURCE_NAME,
            latitude=float(data.get("latitude", config.weather_latitude)),
            longitude=float(data.get("longitude", config.weather_longitude)),
        )

    def _drop_old_calls(self, now: float) -> None:
        one_hour = 60 * 60
        while self._calls and now - self._calls[0] > one_hour:
            self._calls.popleft()


weather_service = WeatherService()
