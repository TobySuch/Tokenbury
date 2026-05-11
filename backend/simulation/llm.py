import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


class LLMError(Exception):
    pass


def call_llm(prompt: str) -> str:
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    payload = json.dumps({
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tokenbury.com",
            "X-Title": "Tokenbury-on-Sea",
            "X-OpenRouter-Categories": "game, roleplay",
        },
        method="POST",
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                raise LLMError(f"OpenRouter HTTP {exc.code}: {exc.reason}") from exc
            retry_after = exc.headers.get("Retry-After")
            delay = min(int(retry_after), 60) if retry_after else 2**attempt
            logger.warning(
                "OpenRouter %d — retrying in %ds (attempt %d/%d)",
                exc.code,
                delay,
                attempt + 1,
                MAX_RETRIES,
            )
            time.sleep(delay)

    raise LLMError("Exhausted retries")
