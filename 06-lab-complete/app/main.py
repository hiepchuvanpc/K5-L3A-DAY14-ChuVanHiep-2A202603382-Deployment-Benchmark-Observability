"""
Production AI Agent — Part 6 Final Project
"""
import sys
import time
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.redis_client import redis_healthy
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost
from utils.mock_llm import ask as llm_ask


# ──────────────────────────────────────────────────────────
# Tiêu chí 10: Structured JSON Logging
# ──────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    """Mỗi dòng log xuất ra định dạng JSON hợp lệ."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts": self.formatTime(record, self.datefmt),
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        return json.dumps(log_obj)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("app.main")

_in_flight = 0


# ──────────────────────────────────────────────────────────
# Tiêu chí 11: Graceful Shutdown qua FastAPI Lifespan
# ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "port": settings.port, "env": settings.environment}))
    yield
    # Khi nhận SIGTERM: đợi in-flight requests xử lý xong
    logger.info(json.dumps({"event": "shutdown_start", "in_flight": _in_flight}))
    deadline = time.time() + 20.0
    while _in_flight > 0 and time.time() < deadline:
        await asyncio.sleep(0.05)
    logger.info(json.dumps({"event": "shutdown_complete"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def track_in_flight(request: Request, call_next):
    global _in_flight
    _in_flight += 1
    try:
        return await call_next(request)
    finally:
        _in_flight -= 1


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


# ──────────────────────────────────────────────────────────
# Tiêu chí 4 & 5: Health & Readiness
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe: Luôn trả 200 khi process đang chạy."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    """Readiness probe: 200 khi sẵn sàng, 503 khi Redis không kết nối được."""
    if not redis_healthy():
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: Redis is disconnected",
        )
    return {"status": "ready", "redis": "connected"}


# ──────────────────────────────────────────────────────────
# Tiêu chí 6, 7, 8: POST /ask (Auth, Rate Limiting, Cost Guard)
# ──────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    record_cost(input_tokens, output_tokens)

    logger.info(json.dumps({
        "event": "ask_success",
        "question_len": len(body.question),
        "answer_len": len(answer),
    }))

    return {"question": body.question, "answer": answer}
