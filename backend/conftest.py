import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    # Test databases reuse primary keys, so stale entries would leak between tests.
    cache.clear()
    yield
    cache.clear()
