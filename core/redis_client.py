"""Клиент для работы с Redis."""

import redis.asyncio as aioredis

from core.config import settings


class RedisClient:
    """Singleton для работы с Redis."""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_pool(self):
        """Получить пул соединений с Redis."""
        if self._pool is None:
            self._pool = aioredis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=10,
                decode_responses=True,
            )
        return self._pool

    async def get_client(self):
        """Получить клиент Redis."""
        pool = await self.get_pool()
        return aioredis.Redis(connection_pool=pool)

    async def close(self):
        """Закрыть соединение с Redis."""
        if self._pool:
            await self._pool.disconnect()
            self._pool = None


# Глобальный экземпляр
redis_client = RedisClient()


async def get_redis():
    """Dependency для получения Redis клиента."""
    return await redis_client.get_client()
