import logging

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_MISSING = object()


def cached(key, timeout, fn):
    """Return the cached value for key, computing and storing it on a miss.

    Keys should embed a version (a max seq, an immutable id) so entries never
    need invalidating. A cache outage degrades to calling fn() directly.
    """
    try:
        value = cache.get(key, _MISSING)
    except RedisError:
        logger.warning("Cache get failed for %s", key, exc_info=True)
        return fn()
    if value is not _MISSING:
        return value
    value = fn()
    try:
        cache.set(key, value, timeout)
    except RedisError:
        logger.warning("Cache set failed for %s", key, exc_info=True)
    return value
