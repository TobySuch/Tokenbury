"""Prompt assembly. ``build_player_prompt`` is pure and takes no Game/Player;
``build_prompt_for`` is the DB-touching pipeline the engine uses."""

from dataclasses import dataclass, field

from werewolf.config import game_config
from werewolf.notes import current_notes
from werewolf.visibility import (
    RosterEntry,
    VisibleEvent,
    build_roster,
    events_visible_to,
    own_role_info,
)


@dataclass(frozen=True)
class PlayerView:
    player_id: int
    name: str
    role: str
    talkativeness: int
    win_condition: str
    wolf_label: str | None
    teammate_name: str | None
    teammate_label: str | None


@dataclass(frozen=True)
class Turn:
    phase: str
    day: int
    kind: str  # wolf_chat | seer_notes | discussion | vote | day_notes
    allowed_tools: list[str] = field(default_factory=list)
    extra: str = ""


PERSONA_LINES = {
    1: "You speak up rarely, and only with something solid.",
    2: "You tend to stay quiet and speak only when you have a point to make.",
    3: "You speak up when you have something to add, no more and no less.",
    4: "You like to join the conversation and share your thoughts often.",
    5: "You are very talkative and are usually in the thick of any discussion.",
}

RULES = """\
You are playing Werewolf in the sleepy English seaside town of Tokenbury-on-Sea.

Setup: 7 players: 2 wolves, 1 seer and 4 villagers. Roles are secret.
Each day plays out in this order:
- Night: the two wolves chat privately and choose someone to kill. They are \
shown to each other as Wolf A and Wolf B. The seer may be listening to this \
chat, but only sees the speakers as Wolf A and Wolf B, never their names, and \
cannot speak or act at night.
- Morning: the victim's death is announced.
- Discussion: everyone alive may speak. Everything said is public.
- Vote: every living player secretly votes for a player, or for no one. The \
player with the most votes is eliminated. A tie, or a majority voting for no \
one, eliminates nobody.
- Then everyone's day notes are written and the next night begins.
The wolves win when they equal or outnumber everyone else. The town wins when \
no wolves remain.

Public rules everyone knows: the seer may be listening to the wolves' night \
chat, so wolves should assume someone is reading it.

General guidance:
- Reason independently. Do not pile onto the first accusation without evidence.
- Ask questions, answer them, and use your notes to track who said what.
- Your log shows only today. Write down anything you will need tomorrow: who \
said what, who you suspect and why, vote results, and what the dead revealed.
- Wolves may lie. Villagers should expect lies."""

WOLF_GUIDANCE = (
    "- In wolf chat, do not name yourself or your teammate. Use Wolf A and Wolf B."
)
SEER_GUIDANCE = (
    "- You cannot speak at night. Work out who the wolves are from how they talk."
)

ROLE_ARTICLES = {"wolf": "a wolf", "seer": "the seer", "villager": "a villager"}

INSTRUCTIONS = {
    "wolf_chat": (
        "It is night. Talk privately with your teammate. Propose a kill target "
        "with kill_target (a living non-wolf); the chat ends early when you "
        "both name the same one."
    ),
    "seer_notes": (
        "It is night. You have read the wolves' chat. You cannot speak. Record "
        "what you noticed in your notes, then pass."
    ),
    "discussion": (
        "It is the day discussion. Speak to everyone, or pass if you have "
        "nothing useful to add."
    ),
    "vote": (
        "It is time to vote. Vote for the player you want eliminated, or for "
        "none. Your ballot is secret until the tally."
    ),
    "day_notes": (
        "The day is over. Record what you will need tomorrow in your notes, then pass."
    ),
}


def player_view(player) -> PlayerView:
    info = own_role_info(player)
    return PlayerView(
        player_id=player.id,
        name=player.name,
        role=player.role,
        talkativeness=player.character.talkativeness,
        win_condition=info.get("win_condition", ""),
        wolf_label=info.get("wolf_label"),
        teammate_name=info.get("teammate_name"),
        teammate_label=info.get("teammate_label"),
    )


def _role_section(view: PlayerView) -> str:
    parts = [
        RULES,
        "",
        f"Your role: {view.role}.",
        f"Your win condition: {view.win_condition}",
    ]
    if view.role == "wolf":
        parts.append(
            f"You are {view.wolf_label}. Your teammate is {view.teammate_name} "
            f"({view.teammate_label})."
        )
        parts.append(WOLF_GUIDANCE)
    elif view.role == "seer":
        parts.append(SEER_GUIDANCE)
    return "\n".join(parts)


def _article(role):
    return ROLE_ARTICLES.get(role, f"a {role}")


def _vote_result(p) -> str:
    parts = ["[Vote]"]
    votes = p.get("votes") or []
    if votes:
        parts.append(
            "; ".join(
                f"{v['voter']} voted for {v['target'] or 'no one'}" for v in votes
            )
            + "."
        )
    tally = ", ".join(f"{k}: {n}" for k, n in (p.get("tally") or {}).items())
    parts.append(f"Tally: {tally}.")
    if p.get("eliminated"):
        parts.append(f"{p['eliminated']} was eliminated.")
    else:
        parts.append("No one was eliminated.")
    return " ".join(parts)


def _death(p) -> str:
    how = (
        "killed in the night"
        if p.get("cause") == "night_kill"
        else "eliminated by vote"
    )
    line = f"{p['player']} was {how}."
    if p.get("role"):
        line += f" They were {_article(p['role'])}."
    return line


def render_event(event: VisibleEvent) -> str:
    """Readable log line; empty string for engine-only types."""
    p = event.payload
    match event.type:
        case "wolf_message":
            line = f"[Night] {event.speaker}: {p['message']}"
            if p.get("kill_target"):
                line += f" (suggests killing {p['kill_target']})"
            return line
        case "wolf_target":
            return f"[Night] The wolves have chosen to kill {p['target']}."
        case "speech":
            return f"{event.speaker}: {p['message']}"
        case "death":
            return _death(p)
        case "vote_result":
            return _vote_result(p)
        case "game_over":
            return f"The game is over. The {p['winner']} won."
        case "role_assigned":
            return f"You were dealt the role of {p['role']}."
        case _:
            return ""


def _roster_line(entry: RosterEntry, reveal: bool) -> str:
    if entry.alive:
        return f"- {entry.name} (alive)"
    if reveal and entry.role:
        return f"- {entry.name} (dead, was {_article(entry.role)})"
    return f"- {entry.name} (dead)"


def build_player_prompt(
    view: PlayerView,
    visible_events: list[VisibleEvent],
    notes: str,
    roster: list[RosterEntry],
    turn: Turn,
    notes_cap: int,
    reveal_role_on_death: bool,
) -> list[dict]:
    persona = (
        f"## Who you are\nYou are {view.name}.\n{PERSONA_LINES[view.talkativeness]}"
    )
    roster_text = "## Players\n" + "\n".join(
        _roster_line(e, reveal_role_on_death) for e in roster
    )
    lines = [line for e in visible_events if (line := render_event(e))]
    log = "## What you can see (today)\n" + (
        "\n".join(lines) if lines else "(Nothing has happened yet today.)"
    )
    notes_text = (
        "## Your private notes (only you can see these)\n"
        f"{len(notes)} / {notes_cap} characters used\n"
        f"{notes if notes else '(empty)'}"
    )
    instruction = (
        f"## Your turn\nDay {turn.day}, phase: {turn.phase}.\n"
        f"{INSTRUCTIONS[turn.kind]}\n"
        + (f"{turn.extra}\n" if turn.extra else "")
        + f"Tools you may use: {', '.join(turn.allowed_tools)}.\n"
        "Update your notes before acting if there is anything worth keeping, "
        "then make exactly one action."
    )
    system = "\n\n".join([
        "## Rules and role\n" + _role_section(view),
        persona,
        roster_text,
        log,
    ])
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{notes_text}\n\n{instruction}"},
    ]


def build_prompt_for(player, turn: Turn) -> list[dict]:
    """Full pipeline through the visibility boundary (touches the DB)."""
    cfg = game_config(player.game)
    return build_player_prompt(
        player_view(player),
        events_visible_to(player, day=turn.day),
        current_notes(player),
        build_roster(player),
        turn,
        cfg["notes_max_chars"],
        cfg["reveal_role_on_death"],
    )
