from django.utils.cache import patch_cache_control

# Data that can still change: polled endpoints, admin-editable content.
LIVE = 10
# Data that never changes once written: completed ticks, finished games.
IMMUTABLE = 60 * 60 * 24


def cache_public(response, seconds):
    """Let browsers and Cloudflare cache a successful public API response."""
    if response.status_code == 200:
        patch_cache_control(response, public=True, max_age=seconds, s_maxage=seconds)
    return response
