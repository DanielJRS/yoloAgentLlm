import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.config import config
from services.event_repository import init_db, list_recent
from services.external_data_client import external_data_client
from services.monitoring_agent import agent
from services.ollama_client import ollama
from services.schemas import AgentStatus, ChatRequest, ChatResponse
from services.video_monitor import monitor
from services.weather_repository import init_weather_db
from services.weather_service import WeatherUnavailable, weather_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_weather_db()
    monitor.start()
    try:
        yield
    finally:
        monitor.stop()
        await ollama.aclose()
        await external_data_client.aclose()


config.captures_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AgroVision AI", lifespan=lifespan)
if config.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


app.mount("/static", StaticFiles(directory=config.base_dir / "static"), name="static")
templates = Jinja2Templates(directory=str(config.base_dir / "templates"))


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/camera/status")
def camera_status():
    return monitor.status()


@app.get("/events")
def events():
    return {"events": [asdict(e) for e in list_recent(limit=50)]}


@app.get("/external/weather")
async def external_weather():
    try:
        snapshot = await weather_service.get_snapshot()
    except WeatherUnavailable as exc:
        return {"available": False, "reason": str(exc), "snapshot": None}
    return {"available": True, "snapshot": snapshot}


@app.get("/frame")
def frame():
    jpeg = monitor.latest_jpeg()
    if jpeg is None:
        return Response(status_code=503)
    return Response(content=jpeg, media_type="image/jpeg")


@app.get("/video_feed")
def video_feed():
    boundary = "frame"

    async def gen():
        while True:
            jpeg = monitor.latest_jpeg()
            if jpeg is not None:
                yield (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode("ascii") + jpeg + b"\r\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(
        gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}"
    )


@app.get("/agent/status", response_model=AgentStatus)
async def agent_status():
    return await agent.status()


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    reply = await agent.chat(payload.message)
    return ChatResponse(reply=reply)
