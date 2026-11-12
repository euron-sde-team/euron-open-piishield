"""Wires together the long-lived objects one application instance needs: the database,
the cache/KV backend, and the vault's sealer. Built once in the app factory's lifespan and
swappable in tests through ``app.dependency_overrides`` / direct construction."""

from __future__ import annotations

from dataclasses import dataclass

from piishield.core.config import Settings
from piishield.core.db import Database
from piishield.core.kv import KV, create_kv
from piishield.core.sealing import Sealer, build_sealer


@dataclass
class Container:
    settings: Settings
    db: Database
    kv: KV
    sealer: Sealer

    @classmethod
    def build(cls, settings: Settings) -> Container:
        db = Database(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        kv = create_kv(settings.redis_url, settings.memory_cache_max_bytes)
        sealer = build_sealer(settings.key_mode, settings.local_master_key, settings.kms_key_id)
        return cls(settings=settings, db=db, kv=kv, sealer=sealer)

    async def close(self) -> None:
        await self.db.dispose()
        await self.kv.close()
