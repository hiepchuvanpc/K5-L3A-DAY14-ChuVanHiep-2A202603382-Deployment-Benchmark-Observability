"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis
from app.config import settings

_client = None


def get_redis():
    """Lấy hoặc khởi tạo Redis client an toàn."""
    global _client
    if _client is None and settings.redis_url:
        try:
            _client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
        except Exception:
            _client = None
    return _client


def redis_healthy() -> bool:
    """Kiểm tra sức khỏe kết nối Redis (dùng cho GET /ready)."""
    try:
        client = get_redis()
        if client is None:
            return False
        return bool(client.ping())
    except Exception:
        return False
