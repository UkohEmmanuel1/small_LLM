"""small_LLM public chat and OpenAI-compatible API."""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_NAME = "small_LLM"
MODEL = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct:cheapest")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_URL = os.getenv("HF_CHAT_COMPLETIONS_URL", "https://router.huggingface.co/v1/chat/completions")
API_KEYS = {key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()}
MAX_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "512"))
RATE_LIMIT = int(os.getenv("DEMO_REQUESTS_PER_MINUTE", "8"))

app = FastAPI(
    title="small_LLM API",
    description="A lightweight chat product powered by open-weight language models. OpenAI-compatible chat completions.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory="static"), name="static")

_requests: dict[str, deque[float]] = defaultdict(deque)


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    model: str | None = Field(default=None, max_length=160)
    messages: list[Message] = Field(min_length=1, max_length=30)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=256, ge=1, le=MAX_TOKENS)
    stream: bool = False


def check_demo_limit(request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _requests[host]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Demo rate limit reached. Try again in a minute.")
    bucket.append(now)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if not API_KEYS:
        raise HTTPException(
            status_code=503,
            detail="Developer API is not configured yet. The operator must set API_KEYS on the server.",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token not in API_KEYS:
        raise HTTPException(status_code=401, detail="A valid Bearer API key is required.")


async def run_inference(payload: ChatRequest) -> dict:
    if payload.model and payload.model != MODEL:
        raise HTTPException(status_code=400, detail=f"This deployment serves only the configured model: {MODEL}")
    if not HF_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="The model provider is not configured. Set HF_TOKEN in the deployment environment.",
        )
    body = {
        "model": MODEL,
        "messages": [m.model_dump() for m in payload.messages],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
            response = await client.post(
                HF_URL,
                headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
                json=body,
            )
        if response.status_code == 401:
            raise HTTPException(status_code=502, detail="The configured model-provider token was rejected.")
        if response.status_code == 429:
            raise HTTPException(status_code=503, detail="The model provider is busy or its quota is exhausted. Try again later.")
        if response.status_code >= 400:
            detail = "The model provider could not complete this request."
            try:
                detail = response.json().get("error", detail)
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=str(detail)[:500])
        return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Model inference timed out. Please retry.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not connect to the model provider.")


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": APP_NAME, "model": MODEL, "provider_configured": bool(HF_TOKEN)}


@app.get("/v1/models", dependencies=[Depends(require_api_key)])
async def models():
    return {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "small_LLM"}]}


@app.post("/api/chat", dependencies=[Depends(check_demo_limit)])
async def demo_chat(payload: ChatRequest):
    return await run_inference(payload)


@app.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
async def chat_completions(payload: ChatRequest):
    if payload.stream:
        raise HTTPException(status_code=400, detail="Streaming is not enabled yet. Set stream=false.")
    return await run_inference(payload)
