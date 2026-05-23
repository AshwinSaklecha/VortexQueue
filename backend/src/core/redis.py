import redis
from src.core.config import settings

# One connection pool for the entire process — shared across all imports
_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,   # always work with str, never bytes
    max_connections=50,
)


def get_redis() -> redis.Redis:
    """Return a Redis client backed by the shared connection pool."""
    return redis.Redis(connection_pool=_pool)
