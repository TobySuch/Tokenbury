import json
import urllib.error
import urllib.request

from django.conf import settings


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

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise LLMError(f"OpenRouter HTTP {exc.code}: {exc.reason}") from exc

    return body["choices"][0]["message"]["content"]
