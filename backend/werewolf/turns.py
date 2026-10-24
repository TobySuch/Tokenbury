"""The turn contract: one player turn, with validation, retries and fallback."""

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace

from simulation.llm import LLMError
from werewolf.agents import (
    AgentResponse,
    ToolCall,
    WerewolfAgent,
    build_raw,
    parse_arguments,
)
from werewolf.config import game_config
from werewolf.models import AgentCall, Game
from werewolf.notes import NotesError, append_note, replace_notes
from werewolf.prompts import Turn
from werewolf.tools import (
    NOTE_TOOLS,
    TERMINAL_TOOLS,
    ValidationContext,
    tools_for,
    validate_tool_call,
)

MAX_RETRIES = 2
NUDGE = "You must respond by calling one of the available tools."


class BudgetExceeded(Exception):
    pass


@dataclass
class TurnResult:
    action: str  # speak | pass | vote
    args: dict
    fallback: bool


def check_budget(game: Game) -> None:
    """Abort the game and raise if it has used up its agent-call budget."""
    if AgentCall.objects.filter(game=game).count() >= game_config(game)["call_budget"]:
        game.status = Game.Status.ABORTED
        game.save(update_fields=["status"])
        raise BudgetExceeded(f"Game {game.pk} exceeded its call budget")


def log_call(
    game: Game,
    player,
    messages: list[dict],
    response_or_error: AgentResponse | Exception,
    latency_ms: int,
) -> AgentCall:
    if isinstance(response_or_error, Exception):
        response = {"error": f"{type(response_or_error).__name__}: {response_or_error}"}
        tokens_in = tokens_out = 0
    else:
        resp = response_or_error
        response = {
            "content": resp.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "raw_arguments": tc.raw_arguments}
                for tc in resp.tool_calls
            ],
        }
        tokens_in, tokens_out = resp.tokens_in, resp.tokens_out
    return AgentCall.objects.create(
        game=game,
        player=player,
        prompt=json.dumps(messages),
        response=json.dumps(response),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=max(int(latency_ms), 0),
    )


def recorded_responses(game: Game) -> Iterator[AgentResponse | Exception]:
    """Rebuild a game's agent responses (errors as LLMError) for ReplayAgent."""
    for call in AgentCall.objects.filter(game=game).order_by("id"):
        data = json.loads(call.response)
        if "error" in data:
            yield LLMError(data["error"])
            continue
        tool_calls = [
            ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=parse_arguments(tc["raw_arguments"]),
                raw_arguments=tc["raw_arguments"],
            )
            for tc in data["tool_calls"]
        ]
        content = data["content"]
        yield AgentResponse(
            tool_calls,
            content,
            call.tokens_in,
            call.tokens_out,
            build_raw(content, tool_calls),
        )


def _fallback(turn: Turn) -> TurnResult:
    if turn.kind == "vote":
        return TurnResult("vote", {"target": "none"}, fallback=True)
    return TurnResult("pass", {}, fallback=True)


def _run_note(player, call: ToolCall) -> str:
    try:
        if call.name == "append_note":
            append_note(player, call.arguments["text"])
        else:
            replace_notes(player, call.arguments["text"])
    except NotesError as exc:
        return f"Error: {exc}"
    return "Notes updated."


def run_turn(
    game: Game,
    player,
    agent: WerewolfAgent,
    turn: Turn,
    ctx: ValidationContext,
    messages: list[dict],
) -> TurnResult:
    """Run one turn. Writes notes and AgentCalls but never GameEvents."""
    if not ctx.actor_name:
        ctx = replace(ctx, actor_name=player.name)
    tools = tools_for(turn.kind, ctx.speech_max_chars)
    max_notes = game_config(game)["max_note_calls_per_turn"]
    messages = list(messages)
    note_calls = 0
    appended: set[str] = set()

    for _attempt in range(MAX_RETRIES + 1):
        check_budget(game)
        started = time.monotonic()
        try:
            resp = agent.respond(messages, tools)
        except Exception as exc:  # noqa: BLE001 - any agent failure is a failed attempt
            log_call(game, player, messages, exc, (time.monotonic() - started) * 1000)
            continue
        log_call(game, player, messages, resp, (time.monotonic() - started) * 1000)

        results = []
        # Pass 1: every note call is processed, whatever its position relative
        # to the terminal call. Pass 2: terminal calls are validated in order.
        for call in resp.tool_calls:
            if call.arguments is None:
                results.append((call, "Error: arguments must be a JSON object."))
                continue
            if call.name not in NOTE_TOOLS:
                continue
            note_calls += 1
            error = validate_tool_call(call.name, call.arguments, ctx)
            if error is None and note_calls > max_notes:
                error = "note call limit reached"
            if error:
                results.append((call, f"Error: {error}"))
            elif call.name == "append_note" and call.arguments["text"] in appended:
                # A resent note still counts toward the limit but is not rewritten.
                results.append((call, "Note already saved this turn."))
            else:
                if call.name == "append_note":
                    appended.add(call.arguments["text"])
                results.append((call, _run_note(player, call)))
        for call in resp.tool_calls:
            if call.arguments is None or call.name in NOTE_TOOLS:
                continue
            error = validate_tool_call(call.name, call.arguments, ctx)
            if error:
                results.append((call, f"Error: {error}"))
            elif call.name in TERMINAL_TOOLS:
                return TurnResult(call.name, call.arguments, fallback=False)

        messages.append(resp.raw)
        messages.extend(
            {"role": "tool", "tool_call_id": call.id, "content": text}
            for call, text in results
        )
        if not resp.tool_calls:
            messages.append({"role": "user", "content": NUDGE})

    return _fallback(turn)
