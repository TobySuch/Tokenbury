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

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "LLM request headers: %s\nLLM request body: %s",
            dict(req.headers),
            payload.decode(),
        )

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                resp_headers = dict(resp.headers)
                raw = resp.read()
                body = json.loads(raw)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "LLM response headers: %s\nLLM response body: %s",
                    resp_headers,
                    raw.decode(),
                )
            if "error" in body:
                err = body["error"]
                code = err.get("code")
                retry_after = (
                    err.get("metadata", {}).get("retry_after_seconds")
                    if isinstance(err.get("metadata"), dict)
                    else None
                )
                logger.warning("OpenRouter error body: %s", err)
                if code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                    delay = min(int(retry_after), 60) if retry_after else 2**attempt
                    logger.warning(
                        "Retrying in %ds (attempt %d/%d)",
                        delay,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue
                raise LLMError(f"OpenRouter error: {err}")
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode(errors="replace")
            logger.warning(
                "OpenRouter %d — headers: %s\nbody: %s",
                exc.code,
                dict(exc.headers) if exc.headers else {},
                err_body,
            )
            if exc.code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                raise LLMError(f"OpenRouter HTTP {exc.code}: {exc.reason}") from exc
            # Prefer retry_after_seconds from OpenRouter's JSON body; fall back to
            # the Retry-After header, then exponential backoff.
            try:
                meta = json.loads(err_body).get("error", {}).get("metadata") or {}
                retry_after_body = meta.get("retry_after_seconds")
            except json.JSONDecodeError:
                retry_after_body = None
            retry_after_header = exc.headers.get("Retry-After")
            raw_delay = retry_after_body or retry_after_header
            delay = min(int(raw_delay), 60) if raw_delay else 2**attempt
            logger.warning(
                "Retrying in %ds (attempt %d/%d)",
                delay,
                attempt + 1,
                MAX_RETRIES,
            )
            time.sleep(delay)

    raise LLMError("Exhausted retries")
