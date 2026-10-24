"""Tool schemas and pure validation for agent turns (never touches the DB)."""

import re
from dataclasses import dataclass

TERMINAL_TOOLS = {"speak", "pass", "vote"}
NOTE_TOOLS = {"append_note", "replace_notes"}


def function_tool(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


def _speak(wolf_chat):
    props = {"message": {"type": "string", "description": "What you say."}}
    if wolf_chat:
        props["kill_target"] = {
            "type": "string",
            "description": "Optional: the living non-wolf you propose to kill.",
        }
    return function_tool(
        "speak",
        "Say something to the wolves (private)."
        if wolf_chat
        else "Say something to everyone.",
        props,
        ["message"],
    )


_PASS = function_tool("pass", "End your turn without speaking.")
_VOTE = function_tool(
    "vote",
    "Cast your secret vote for a player, or for no one.",
    {
        "target": {
            "type": "string",
            "description": "A living player's name, or 'none'.",
        }
    },
    ["target"],
)
_APPEND = function_tool(
    "append_note",
    "Add text to the end of your private notes.",
    {"text": {"type": "string"}},
    ["text"],
)
_REPLACE = function_tool(
    "replace_notes",
    "Rewrite your whole private notes. Warning: rewriting can drop earlier "
    "facts, so prefer append_note unless you are condensing.",
    {"text": {"type": "string", "description": "The complete new notes."}},
    ["text"],
)


def tools_for(turn_kind: str) -> list[dict]:
    terminal = {
        "wolf_chat": [_speak(True), _PASS],
        "seer_notes": [_PASS],
        "discussion": [_speak(False), _PASS],
        "vote": [_VOTE],
        "day_notes": [_PASS],
    }[turn_kind]
    return [*terminal, _APPEND, _REPLACE]


@dataclass
class ValidationContext:
    turn_kind: str
    actor_role: str
    actor_alive: bool
    wolf_names: list[str]
    living_names: list[str]
    living_non_wolf_names: list[str]
    speech_max_chars: int
    actor_name: str = ""


def match_name(name, candidates, key=str):
    """Return the candidate whose key matches name (strip + casefold), else None."""
    if not isinstance(name, str):
        return None
    wanted = name.strip().casefold()
    return next((c for c in candidates if key(c).casefold() == wanted), None)


def _text_error(args, key, label):
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        return f"{label} must be a non-empty string."
    return None


def _validate_speak(args, ctx):
    if err := _text_error(args, "message", "'message'"):
        return err
    message = args["message"]
    if len(message) > ctx.speech_max_chars:
        return (
            f"Message is {len(message)} characters; the maximum is "
            f"{ctx.speech_max_chars}. Shorten it."
        )
    if ctx.turn_kind != "wolf_chat":
        return None
    for name in ctx.wolf_names:
        if re.search(rf"\b{re.escape(name)}\b", message, re.IGNORECASE):
            return "Do not name wolves; use Wolf A / Wolf B."
    target = args.get("kill_target")
    if target is not None and match_name(target, ctx.living_non_wolf_names) is None:
        return "kill_target must be the name of a living non-wolf player."
    return None


def _validate_vote(args, ctx):
    target = args.get("target")
    if not isinstance(target, str) or not target.strip():
        return "'target' must be a player's name or 'none'."
    if target.strip().casefold() == "none":
        return None
    others = [n for n in ctx.living_names if n.casefold() != ctx.actor_name.casefold()]
    if match_name(target, others) is None:
        return "target must be a living player other than yourself, or 'none'."
    return None


def validate_tool_call(name, args, ctx: ValidationContext) -> str | None:
    if name not in TERMINAL_TOOLS | NOTE_TOOLS:
        return f"Unknown tool {name!r}."
    if not ctx.actor_alive:
        return "You are dead and cannot act."
    allowed = {t["function"]["name"] for t in tools_for(ctx.turn_kind)}
    if name not in allowed:
        if name == "speak" and ctx.actor_role == "seer":
            return "The seer cannot speak at night."
        return (
            f"Tool {name!r} is not allowed now. Allowed: {', '.join(sorted(allowed))}."
        )
    if not isinstance(args, dict):
        return "Tool arguments must be an object."
    if name == "speak":
        return _validate_speak(args, ctx)
    if name == "vote":
        return _validate_vote(args, ctx)
    if name in NOTE_TOOLS:
        return _text_error(args, "text", "'text'")
    return None
