import logging

import httpx

from services.config import config

logger = logging.getLogger("uvicorn.error")


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=config.ollama_timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def is_online(self) -> bool:
        base = config.ollama_url.rsplit("/api/", 1)[0]
        try:
            r = await self._client.get(f"{base}/api/tags", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": config.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": config.ollama_keep_alive,
        }
        try:
            r = await self._client.post(config.ollama_url, json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("ollama chat failed: %s", exc)
            raise OllamaError(str(exc)) from exc

        data = r.json()
        message = data.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise OllamaError("resposta vazia do Ollama")
        return content


ollama = OllamaClient()
