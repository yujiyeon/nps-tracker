"""Redis 캐시 서비스 - API 응답 캐싱"""
import json
from typing import Any

import redis
from loguru import logger

from config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def get_cached(key: str) -> Any | None:
    try:
        raw = get_redis().get(key)
        return json.loads(raw) if raw else None
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.warning(f"캐시 조회 실패 ({key}): {e}")
        return None


def set_cached(key: str, value: Any, ttl: int = 3600) -> None:
    try:
        get_redis().setex(key, ttl, json.dumps(value, default=str))
    except redis.RedisError as e:
        logger.warning(f"캐시 저장 실패 ({key}): {e}")


def delete_cached(key: str) -> None:
    try:
        get_redis().delete(key)
    except redis.RedisError as e:
        logger.warning(f"캐시 삭제 실패 ({key}): {e}")
