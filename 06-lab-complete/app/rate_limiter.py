"""
Rate limiting (tiêu chí 7).
"""
import time
import secrets
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis


def check_rate_limit(key: str) -> None:
    """Kiểm tra giới hạn rate limit sử dụng Redis sliding window."""
    client = get_redis()
    if client is None:
        return

    now = time.time()
    window_start = now - 60.0
    redis_key = f"rate_limit:{key}"

    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {f"{now}_{secrets.token_hex(4)}": now})
        pipe.expire(redis_key, 65)
        results = pipe.execute()
        count = results[1]
    except Exception:
        return

    if count >= settings.rate_limit_per_minute:
        retry_after = 60
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
