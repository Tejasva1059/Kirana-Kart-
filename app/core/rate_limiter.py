import asyncio
import time
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.core.exceptions import RateLimitExceededException
from app.core.logging import logger

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class BaseRateLimiter:
    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        raise NotImplementedError


class InMemoryRateLimiter(BaseRateLimiter):
    """
    In-memory sliding window rate limiter.
    Suitable for local development and automated testing only.
    NOT suitable for distributed, multi-instance production deployments!
    """

    def __init__(self):
        self._records: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
        logger.warning(
            "InMemoryRateLimiter active: Note that in-memory rate limiting is only suitable for local development "
            "and single-process testing, and is UNSUITABLE for distributed multi-instance production deployments. "
            "Configure REDIS_URL for production."
        )

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            timestamps = self._records.get(key, [])
            # Prune old timestamps
            valid_timestamps = [ts for ts in timestamps if ts > window_start]

            if len(valid_timestamps) >= max_requests:
                oldest_valid = valid_timestamps[0]
                retry_after = max(1, int(oldest_valid + window_seconds - now))
                self._records[key] = valid_timestamps
                return False, retry_after

            valid_timestamps.append(now)
            self._records[key] = valid_timestamps
            return True, 0

    async def reset(self, key: Optional[str] = None) -> None:
        async with self._lock:
            if key:
                self._records.pop(key, None)
            else:
                self._records.clear()


class RedisRateLimiter(BaseRateLimiter):
    """Distributed Redis sliding window rate limiter."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"rl:{key}"

        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            results = await pipe.execute()

            current_count = results[1]
            oldest_entry = results[2]

            if current_count >= max_requests:
                oldest_score = oldest_entry[0][1] if oldest_entry else window_start
                retry_after = max(1, int(oldest_score + window_seconds - now))
                return False, retry_after

            pipe = self.redis.pipeline()
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds + 5)
            await pipe.execute()
            return True, 0
        except Exception as exc:
            logger.error(f"Redis rate limiter error, failing open: {exc}")
            return True, 0


_limiter_instance: Optional[BaseRateLimiter] = None


def get_rate_limiter() -> BaseRateLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        if settings.REDIS_URL and aioredis is not None:
            try:
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                _limiter_instance = RedisRateLimiter(client)
                logger.info("Initialized Redis distributed rate limiter.")
            except Exception as exc:
                logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {exc}. Falling back to in-memory.")
                _limiter_instance = InMemoryRateLimiter()
        else:
            _limiter_instance = InMemoryRateLimiter()
    return _limiter_instance


async def enforce_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    message: str = "Rate limit exceeded. Please try again later.",
) -> None:
    limiter = get_rate_limiter()
    allowed, retry_after = await limiter.is_allowed(key, max_requests, window_seconds)
    if not allowed:
        raise RateLimitExceededException(message=message, retry_after=retry_after)
