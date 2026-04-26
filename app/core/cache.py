from collections.abc import Generator

import redis

from app.core.config import get_settings


def get_redis() -> Generator[redis.Redis, None, None]:
    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        yield client
    finally:
        client.close()

