import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("uvicorn.error")


class ExternalDataError(RuntimeError):
    pass


class ExternalDataClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
        retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = await self._client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ExternalDataError("resposta externa nao e um objeto JSON")
                return data
            except (httpx.HTTPError, ValueError, ExternalDataError) as exc:
                last_error = exc
                logger.warning("external data request failed: %s", exc)
                if attempt < retries:
                    await asyncio.sleep(backoff_seconds * (2**attempt))
        raise ExternalDataError(str(last_error) if last_error else "falha externa")


external_data_client = ExternalDataClient()

