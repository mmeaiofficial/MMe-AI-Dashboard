"""Fixed-window rate limits in Redis (in-memory fallback for local development and tests)."""
from __future__ import annotations

import threading
import time
from typing import Protocol


class Limiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool: ...


class MemoryLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time() // window_seconds)
        with self._lock:
            b, n = self._counts.get(key, (bucket, 0))
            if b != bucket:
                b, n = bucket, 0
            n += 1
            self._counts[key] = (b, n)
            return n <= limit


class RedisLimiter:
    def __init__(self, url: str) -> None:
        import redis  # imported lazily so unit tests don't need the package
        self._r = redis.Redis.from_url(url)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time() // window_seconds)
        k = f"rl:{key}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(k)
        pipe.expire(k, window_seconds + 5)
        count, _ = pipe.execute()
        return int(count) <= limit


_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        import os

        from .config import load_settings
        s = load_settings()
        backend = os.environ.get("RATE_LIMIT_BACKEND", "redis")
        if backend == "memory" and s.is_production:
            raise RuntimeError("RATE_LIMIT_BACKEND=memory is not allowed in production")
        _limiter = MemoryLimiter() if backend == "memory" else RedisLimiter(s.redis_url)
    return _limiter


# name: (limit, window seconds)
LIMITS = {
    "login_ip": (20, 300),
    "login_email": (8, 900),
    "mfa_user": (6, 300),
    "invite_user": (30, 3600),
    "export_user": (20, 3600),
    "api_user": (600, 60),
    "assistant_user": (60, 3600),
}
