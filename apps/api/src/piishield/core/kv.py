"""A small key-value interface with two backends: Redis, or process memory.

PIIShield must run with no Redis at all (a privacy/detection tool degrades predictably,
never fails closed): the policy snapshot cache, the tokenization scope map and the
dashboard aggregate cache all go through :class:`KV`. With ``REDIS_URL`` set, state is
shared by every replica; without it, each process keeps its own, which is exact for a
single replica and documented as such.

Unlike a security enforcement gate, a KV outage here never blocks a scan or a protect
call: the policy service falls back to a fresh database read (slower, not wrong), and
tokenization falls back to a durable vault lookup for scope consistency (see
``vault.service``). Nothing is silently skipped; see each caller's fallback.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Protocol

from redis.asyncio import Redis


class KV(Protocol):
    backend: str

    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl_s: int) -> None: ...
    async def incr(self, key: str) -> int: ...
    async def delete(self, key: str) -> None: ...
    async def ping(self) -> None: ...
    async def close(self) -> None: ...


class RedisKV:
    backend = "redis"

    def __init__(self, url: str) -> None:
        self.redis = Redis.from_url(
            url,
            decode_responses=False,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            health_check_interval=15,
            retry_on_timeout=False,
        )

    async def get(self, key: str) -> bytes | None:
        value = await self.redis.get(key)
        if value is None:
            return None
        return value if isinstance(value, bytes) else str(value).encode()

    async def set(self, key: str, value: bytes, ttl_s: int) -> None:
        await self.redis.set(key, value, ex=ttl_s)

    async def incr(self, key: str) -> int:
        return int(await self.redis.incr(key))

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def ping(self) -> None:
        await self.redis.ping()

    async def close(self) -> None:
        await self.redis.aclose()


class MemoryKV:
    """LRU with expiry bounded by entries and bytes. One process only."""

    backend = "memory"

    def __init__(self, max_entries: int = 4096, max_bytes: int = 64_000_000) -> None:
        self._data: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._max = max_entries
        self._max_bytes = max_bytes
        self._bytes = 0

    async def get(self, key: str) -> bytes | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        if hit[0] < time.monotonic():
            self._drop(key)
            return None
        self._data.move_to_end(key)
        return hit[1]

    async def set(self, key: str, value: bytes, ttl_s: int) -> None:
        if len(value) > self._max_bytes:
            return
        self._drop(key)
        self._data[key] = (time.monotonic() + ttl_s, value)
        self._bytes += len(key) + len(value)
        while len(self._data) > self._max or self._bytes > self._max_bytes:
            oldest = next(iter(self._data))
            self._drop(oldest)

    def _drop(self, key: str) -> None:
        old = self._data.pop(key, None)
        if old is not None:
            self._bytes -= len(key) + len(old[1])

    async def delete(self, key: str) -> None:
        self._drop(key)

    async def incr(self, key: str) -> int:
        current = await self.get(key)
        value = int(current or b"0") + 1
        await self.set(key, str(value).encode(), 10 * 365 * 24 * 3600)
        return value

    async def ping(self) -> None:
        return None

    async def close(self) -> None:
        self._data.clear()
        self._bytes = 0


def create_kv(redis_url: str, memory_max_bytes: int = 64_000_000) -> KV:
    return RedisKV(redis_url) if redis_url else MemoryKV(max_bytes=memory_max_bytes)
