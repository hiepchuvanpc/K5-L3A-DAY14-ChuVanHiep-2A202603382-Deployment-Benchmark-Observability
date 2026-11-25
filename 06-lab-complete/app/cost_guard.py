"""
Cost guard (tiêu chí 8).
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    client = get_redis()
    if client is None:
        return

    today = time.strftime("%Y-%m-%d")
    cost_key = f"cost:{today}"
    try:
        current_cost = float(client.get(cost_key) or 0.0)
    except Exception:
        current_cost = 0.0

    if current_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": current_cost,
                "budget_usd": settings.daily_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    req_cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    client = get_redis()
    if client is not None:
        today = time.strftime("%Y-%m-%d")
        cost_key = f"cost:{today}"
        try:
            client.incrbyfloat(cost_key, req_cost)
            client.expire(cost_key, 32 * 86400)
        except Exception:
            pass
    return req_cost
