import asyncio
import json
import time
from typing import Any, Optional
from src.app.observability.logging import get_logger

logger = get_logger("cache")


class MemoryCacheBackend:
    """In-memory TTL cache used as a standalone or fallback cache."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            val, expiry = item
            if expiry > 0 and time.time() > expiry:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        async with self._lock:
            expiry = time.time() + ttl if ttl > 0 else 0
            self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class CacheService:
    """Unified cache service that automatically switches between Redis and Memory."""

    def __init__(self, enabled: bool = False, host: str = "localhost", port: int = 6379, password: str = "") -> None:
        self.enabled = enabled
        self.host = host
        self.port = port
        self.password = password
        self._memory = MemoryCacheBackend()
        self._redis_client: Any = None
        self._is_redis_ready = False

    async def initialize(self) -> None:
        if not self.enabled:
            logger.info("Redis is DISABLED by configuration. Using internal in-memory cache.")
            return

        try:
            import redis.asyncio as aioredis
            self._redis_client = aioredis.Redis(
                host=self.host,
                port=self.port,
                password=self.password or None,
                decode_responses=True,
                socket_timeout=2.0,
            )
            await self._redis_client.ping()
            self._is_redis_ready = True
            logger.info(f"Connected to Redis successfully at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis at {self.host}:{self.port}: {e}. "
                "Falling back safely to in-memory cache without failing application."
            )
            self._is_redis_ready = False

    async def get(self, key: str) -> Optional[Any]:
        if self.enabled and self._is_redis_ready and self._redis_client:
            try:
                raw = await self._redis_client.get(key)
                if raw is not None:
                    try:
                        return json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        return raw
                return None
            except Exception as e:
                logger.warning(f"Redis get failed for key '{key}': {e}. Falling back to memory cache.")
        return await self._memory.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        payload = json.dumps(value, default=str) if isinstance(value, (dict, list)) else value
        if self.enabled and self._is_redis_ready and self._redis_client:
            try:
                await self._redis_client.set(key, payload, ex=ttl if ttl > 0 else None)
                return
            except Exception as e:
                logger.warning(f"Redis set failed for key '{key}': {e}. Storing in memory fallback.")
        await self._memory.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        if self.enabled and self._is_redis_ready and self._redis_client:
            try:
                await self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed for key '{key}': {e}.")
        await self._memory.delete(key)

    async def close(self) -> None:
        if self._redis_client and self._is_redis_ready:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
        await self._memory.clear()
