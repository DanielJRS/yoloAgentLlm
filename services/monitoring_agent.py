import logging
from collections import deque

from services.config import config
from services.event_repository import Event, list_recent
from services.ollama_client import OllamaError, ollama

logger = logging.getLogger("uvicorn.error")

PROFILE = (
    "Você é o AgroVision AI, um assistente especialista em monitoramento por "
    "visão computacional aplicado ao agronegócio. Você recebe eventos detectados "
    "por um modelo YOLO em uma câmera ao vivo (objetos como pessoas, veículos, "
    "animais) e ajuda o operador humano a interpretar a situação."
)

RULES = [
    "Responda sempre em português do Brasil, em tom profissional e objetivo.",
    "Baseie-se nos eventos recentes fornecidos no contexto. Se não houver eventos relevantes, diga isso claramente.",
    "Não invente detecções. Se o usuário perguntar sobre algo que não está nos eventos, deixe explícito que não foi detectado.",
    "Quando descrever uma situação, cite contagens e a janela de tempo dos eventos.",
    "Você é uma camada de orquestração sobre um LLM, não um modelo de visão. Não tente identificar coisas em imagens — use apenas os rótulos dos eventos.",
]

SHORT_MEMORY_TURNS = 6


class MonitoringAgent:
    def __init__(self) -> None:
        self._memory: deque[dict] = deque(maxlen=SHORT_MEMORY_TURNS * 2)
        self._last_summary: str | None = None

    def _system_prompt(self, events: list[Event]) -> str:
        rules_block = "\n".join(f"- {r}" for r in RULES)
        if events:
            lines = [
                f"- {e.event_time} | {e.label} (confiança {e.confidence:.2f})"
                for e in events
            ]
            events_block = "Eventos recentes (mais novo primeiro):\n" + "\n".join(lines)
        else:
            events_block = "Eventos recentes: nenhum evento registrado até o momento."
        return f"{PROFILE}\n\nRegras:\n{rules_block}\n\n{events_block}"

    async def status(self) -> dict:
        events = list_recent(limit=config.agent_event_limit)
        online = await ollama.is_online()
        return {
            "ollama_online": online,
            "model": config.ollama_model,
            "tracked_classes": list(config.target_classes),
            "recent_events": [
                {
                    "id": e.id,
                    "event_time": e.event_time,
                    "label": e.label,
                    "confidence": e.confidence,
                    "image_path": e.image_path,
                }
                for e in events
            ],
            "last_summary": self._last_summary,
        }

    async def chat(self, user_message: str) -> str:
        events = list_recent(limit=config.agent_event_limit)
        messages: list[dict] = [{"role": "system", "content": self._system_prompt(events)}]
        messages.extend(self._memory)
        messages.append({"role": "user", "content": user_message})

        try:
            reply = await ollama.chat(messages)
        except OllamaError as exc:
            return (
                "Não consegui falar com o Ollama agora. Verifique se o serviço "
                f"está rodando em {config.ollama_url} e se o modelo "
                f"'{config.ollama_model}' está instalado.\nDetalhe técnico: {exc}"
            )

        self._memory.append({"role": "user", "content": user_message})
        self._memory.append({"role": "assistant", "content": reply})
        self._last_summary = reply
        return reply


agent = MonitoringAgent()
