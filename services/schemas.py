from pydantic import BaseModel, Field


class EventOut(BaseModel):
    id: int
    event_time: str
    label: str
    confidence: float
    image_path: str | None = None


class CameraStatus(BaseModel):
    online: bool
    connected: bool
    has_live_frame: bool
    source_type: str
    frames_read: int
    events_saved: int


class AgentStatus(BaseModel):
    ollama_online: bool
    model: str
    tracked_classes: list[str]
    recent_events: list[EventOut]
    last_summary: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
