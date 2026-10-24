"""Agent implementations for werewolf turns.

Deliberately shares no code with the live simulation's agent apart from the
low-level OpenRouter HTTP client.
"""

import itertools
import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings

from simulation.llm import post_chat


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict | None  # None if the raw arguments were not a JSON object
    raw_arguments: str


@dataclass
class AgentResponse:
    tool_calls: list[ToolCall]
    content: str
    tokens_in: int
    tokens_out: int
    raw: dict  # assistant message, appended back into the conversation


class WerewolfAgent(Protocol):
    def respond(self, messages: list[dict], tools: list[dict]) -> AgentResponse: ...


def parse_arguments(raw_arguments: str) -> dict | None:
    try:
        parsed = json.loads(raw_arguments)
    except TypeError, ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_raw(content: str, tool_calls: list[ToolCall]) -> dict:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.raw_arguments},
            }
            for tc in tool_calls
        ]
    return message


class LLMAgent:
    def __init__(self, model: str | None = None, timeout: float | None = None):
        self.model = model
        self.timeout = timeout

    def respond(self, messages: list[dict], tools: list[dict]) -> AgentResponse:
        payload = {
            "model": self.model or settings.WEREWOLF_LLM_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "required",
        }
        body = post_chat(payload, timeout=self.timeout)
        message = body["choices"][0]["message"]
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or ""
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=parse_arguments(raw_args),
                    raw_arguments=raw_args,
                )
            )
        usage = body.get("usage") or {}
        return AgentResponse(
            tool_calls=tool_calls,
            content=message.get("content") or "",
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            raw=message,
        )


Step = list[tuple[str, dict]]


class ScriptedAgent:
    """Canned actions: a callable (messages, tools) -> step, or an iterable of steps."""

    def __init__(self, script: Callable[[list[dict], list[dict]], Step] | Iterable):
        self._script = script if callable(script) else None
        self._steps = None if callable(script) else iter(script)
        self._ids = itertools.count(1)

    def respond(self, messages: list[dict], tools: list[dict]) -> AgentResponse:
        if self._script is not None:
            step = self._script(messages, tools)
        else:
            try:
                step = next(self._steps)
            except StopIteration:
                raise RuntimeError("ScriptedAgent script exhausted") from None
        tool_calls = [
            ToolCall(
                id=f"call_{next(self._ids)}",
                name=name,
                arguments=args,
                raw_arguments=json.dumps(args),
            )
            for name, args in step
        ]
        return AgentResponse(tool_calls, "", 0, 0, build_raw("", tool_calls))


class ReplayAgent:
    """Replays recorded responses; an Exception instance in the stream is raised."""

    def __init__(self, responses: Iterator[AgentResponse | Exception]):
        self._responses = responses

    def respond(self, messages: list[dict], tools: list[dict]) -> AgentResponse:
        item = next(self._responses)
        if isinstance(item, Exception):
            raise item
        return item
