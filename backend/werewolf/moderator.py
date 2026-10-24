"""The discussion moderator: decides who speaks next, or calls time.

It sees public speech plus its own earlier picks only. Nothing here may read
roles, notes or non-public events.
"""

import time
from dataclasses import dataclass, field

from werewolf.agents import WerewolfAgent
from werewolf.config import game_config
from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, Game, GameEvent, Player
from werewolf.rng import rng_for
from werewolf.tools import function_tool
from werewolf.turns import check_budget, log_call

PICK_TOOL = "pick_speaker"
END_TOOL = "end_discussion"
MAX_CONSECUTIVE_PASSES = 3
RECENT_MESSAGES = 10

SYSTEM_PROMPT = """\
You are the moderator of a group discussion among the people of a small town. \
You do not take part; you only decide who speaks next.

After every message, pick who should speak next so the discussion stays lively \
and fair. Favour people who were just addressed or accused, balance \
talkativeness so quieter players get chances, and avoid letting one voice \
dominate. Being named in a message is a hint, not an obligation: someone \
mentioned in passing need not reply.

You may only pick from the list of eligible speakers. You may end the \
discussion once the minimum number of messages has been reached and the \
conversation has run its course. As the maximum approaches, wrap things up. \
Give a one-line reason with every decision.

Respond by calling exactly one tool."""


@dataclass
class DiscussionState:
    messages_used: int = 0
    per_player: dict[int, int] = field(default_factory=dict)
    last_speaker_id: int | None = None
    consecutive_passes: int = 0
    declined: list[int] = field(default_factory=list)
    picks: list[dict] = field(default_factory=list)
    ended: bool = False


def _today(game: Game, **filters):
    return GameEvent.objects.filter(
        game=game, day=game.day_number, phase=Game.Phase.DISCUSSION, **filters
    ).order_by("seq")


def discussion_state(game: Game) -> DiscussionState:
    state = DiscussionState()
    events = _today(game, type__in=["speech", "pass", "moderator_pick"])
    for event in events:
        if event.type == "speech":
            state.messages_used += 1
            state.per_player[event.actor_id] = (
                state.per_player.get(event.actor_id, 0) + 1
            )
            state.last_speaker_id = event.actor_id
            state.consecutive_passes = 0
            state.declined = []
        elif event.type == "pass":
            state.consecutive_passes += 1
            state.declined.append(event.actor_id)
        else:
            state.picks.append(event.payload)
            if event.payload.get("end"):
                state.ended = True
    return state


def eligible_speakers(game: Game, state: DiscussionState) -> list[Player]:
    cap = game_config(game)["discussion_max_per_player"]
    return [
        p
        for p in game.players.filter(alive=True).select_related("character")
        if state.per_player.get(p.id, 0) < cap and p.id != state.last_speaker_id
    ]


def forced_end_reason(game: Game, state: DiscussionState) -> str | None:
    if state.messages_used >= game_config(game)["discussion_max_messages"]:
        return "cap"
    if state.consecutive_passes >= MAX_CONSECUTIVE_PASSES:
        return "passes"
    if not eligible_speakers(game, state):
        return "no_eligible"
    return None


def moderator_tools() -> list[dict]:
    return [
        function_tool(
            PICK_TOOL,
            "Choose who speaks next.",
            {
                "name": {"type": "string", "description": "An eligible speaker."},
                "reason": {"type": "string", "description": "One-line reason."},
            },
            ["name", "reason"],
        ),
        function_tool(
            END_TOOL,
            "End the discussion (only once the minimum messages is reached).",
            {"reason": {"type": "string", "description": "One-line reason."}},
            ["reason"],
        ),
    ]


def build_moderator_prompt(
    roster_rows: list[dict],
    recent_messages: list[str],
    prior_picks: list[tuple[str, str]],
    declined_names: list[str],
    stopwatch: dict,
    eligible_names: list[str],
) -> list[dict]:
    roster = "\n".join(
        f"- {r['name']} ({'alive' if r['alive'] else 'dead'}), "
        f"talkativeness {r['talkativeness']}/5, "
        f"messages so far: {r['messages']}"
        for r in roster_rows
    )
    recent = "\n".join(recent_messages) or "(nobody has spoken yet)"
    picks = "\n".join(f"- {who}: {why}" for who, why in prior_picks) or "(none yet)"
    declined = ", ".join(declined_names) or "(nobody)"
    user = f"""\
Players:
{roster}

Stopwatch: {stopwatch["used"]} of {stopwatch["max"]} messages used \
(you may end the discussion once {stopwatch["min"]} have been used).

Last {RECENT_MESSAGES} messages:
{recent}

Your earlier decisions today:
{picks}

Declined to speak since the last message: {declined}

Eligible to speak next: {", ".join(eligible_names)}

Who speaks next, or is it time to end?"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def moderator_prompt_for(game: Game, state: DiscussionState) -> list[dict]:
    """Gather prompt inputs from public speech and the moderator's own picks only."""
    cfg = game_config(game)
    players = list(game.players.select_related("character"))
    names = {p.id: p.name for p in players}
    roster_rows = [
        {
            "name": p.name,
            "alive": p.alive,
            "talkativeness": p.character.talkativeness,
            "messages": state.per_player.get(p.id, 0),
        }
        for p in players
    ]
    speeches = list(
        _today(game, type="speech", visibility=PUBLIC).select_related("actor")
    )[-RECENT_MESSAGES:]
    recent = [
        f"{names.get(e.actor_id, 'Unknown')}: {e.payload['message']}" for e in speeches
    ]
    prior = [
        ("END" if p["end"] else names.get(p["pick_id"], "Unknown"), p["reason"])
        for p in state.picks
    ]
    return build_moderator_prompt(
        roster_rows,
        recent,
        prior,
        [names.get(i, "Unknown") for i in state.declined],
        {
            "used": state.messages_used,
            "max": cfg["discussion_max_messages"],
            "min": cfg["discussion_min_messages"],
        },
        [p.name for p in eligible_speakers(game, state)],
    )


def fallback_pick(game: Game, state: DiscussionState, eligible: list[Player]) -> Player:
    rng = rng_for(game, "moderator", str(game.day_number), str(len(state.picks)))
    weights = [p.character.talkativeness for p in eligible]
    return rng.choices(eligible, weights=weights, k=1)[0]


def _write(game: Game, payload: dict) -> dict:
    append_event(
        game,
        type="moderator_pick",
        visibility=ENGINE,
        phase=Game.Phase.DISCUSSION,
        payload=payload,
    )
    return payload


def _interpret(call, eligible, state, min_messages) -> tuple[dict | None, str]:
    """Return (payload, "") if the call is valid, else (None, why)."""
    args = call.arguments
    if args is None:
        return None, "arguments were not an object"
    reason = args.get("reason")
    reason = (
        reason.strip()
        if isinstance(reason, str) and reason.strip()
        else "no reason given"
    )
    if call.name == PICK_TOOL:
        name = args.get("name")
        match = None
        if isinstance(name, str):
            match = next(
                (p for p in eligible if p.name.lower() == name.strip().lower()), None
            )
        if match is None:
            return None, f"invalid pick {name!r}"
        return {
            "pick_id": match.id,
            "end": False,
            "reason": reason,
            "source": "llm",
        }, ""
    if call.name == END_TOOL:
        if state.messages_used < min_messages:
            return None, f"end refused before {min_messages} messages"
        return {"pick_id": None, "end": True, "reason": reason, "source": "llm"}, ""
    return None, f"unknown tool {call.name!r}"


def moderate(game: Game, agent: WerewolfAgent, state: DiscussionState) -> dict:
    forced = forced_end_reason(game, state)
    if forced:
        return _write(
            game, {"pick_id": None, "end": True, "reason": forced, "source": "forced"}
        )
    eligible = eligible_speakers(game, state)
    check_budget(game)
    messages = moderator_prompt_for(game, state)
    started = time.monotonic()
    why = "no tool call"
    try:
        resp = agent.respond(messages, moderator_tools())
    except Exception as exc:  # noqa: BLE001 - any failure means fallback
        log_call(game, None, messages, exc, (time.monotonic() - started) * 1000)
        why = f"call failed ({type(exc).__name__})"
    else:
        log_call(game, None, messages, resp, (time.monotonic() - started) * 1000)
        if resp.tool_calls:
            payload, why = _interpret(
                resp.tool_calls[0],
                eligible,
                state,
                game_config(game)["discussion_min_messages"],
            )
            if payload:
                return _write(game, payload)
    chosen = fallback_pick(game, state, eligible)
    return _write(
        game,
        {
            "pick_id": chosen.id,
            "end": False,
            "reason": f"fallback: {why}",
            "source": "fallback",
        },
    )
