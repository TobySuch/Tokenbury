"""Prompt assembly. ``build_player_prompt`` is pure and takes no Game/Player;
``build_prompt_for`` is the DB-touching pipeline the engine uses."""

from dataclasses import dataclass, field

from werewolf.config import game_rules
from werewolf.notes import current_notes
from werewolf.visibility import (
    RosterEntry,
    VisibleEvent,
    build_roster,
    events_visible_to,
    own_role_info,
)


@dataclass(frozen=True)
class PublicRules:
    """Everything the rules text says: public information about this game."""

    player_count: int
    role_counts: dict[str, int]
    lovers_enabled: bool
    reveal_role_on_death: bool


@dataclass(frozen=True)
class PlayerView:
    player_id: int
    name: str
    role: str
    talkativeness: int
    win_condition: str
    wolf_label: str | None
    teammates: tuple[tuple[str, str], ...] = ()  # (name, label) of fellow wolves
    lover_name: str | None = None
    lovers_note: str | None = None


@dataclass(frozen=True)
class Turn:
    phase: str
    day: int
    kind: str  # wolf_chat | doctor | lovers_chat | seer_notes | discussion | vote | day_notes
    allowed_tools: list[str] = field(default_factory=list)
    extra: str = ""


PERSONA_LINES = {
    1: "You speak up rarely, and only with something solid.",
    2: "You tend to stay quiet and speak only when you have a point to make.",
    3: "You speak up when you have something to add, no more and no less.",
    4: "You like to join the conversation and share your thoughts often.",
    5: "You are very talkative and are usually in the thick of any discussion.",
}

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
ROLE_PLURALS = {"wolf": "wolves", "villager": "villagers"}
ROLE_ORDER = ("wolf", "seer", "doctor", "villager")


def _count_phrase(role, n):
    return f"{n} {ROLE_PLURALS.get(role, role + 's') if n != 1 else role}"


def _mix(counts):
    parts = [_count_phrase(r, counts[r]) for r in ROLE_ORDER if counts.get(r)]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _night_lines(rules: PublicRules) -> list[str]:
    wolves = rules.role_counts.get("wolf", 0)
    seer = bool(rules.role_counts.get("seer"))
    if wolves == 1:
        lines = [
            "- Night: the wolf chooses someone to kill."
            + (
                " The seer may be listening, but only sees the speaker as "
                "Wolf A, never a name."
                if seer
                else ""
            )
        ]
    else:
        word = NUMBER_WORDS.get(wolves, str(wolves))
        lines = [
            (
                f"- Night: the {word} wolves chat privately and choose someone to "
                "kill. They are shown to each other as Wolf A, Wolf B and so on."
                + (
                    " The seer may be listening to this chat, but only sees the "
                    "speakers as wolf labels, never their names, and cannot speak "
                    "or act at night."
                    if seer
                    else ""
                )
            )
        ]
    if rules.role_counts.get("doctor"):
        lines.append(
            "  Then the doctor does their rounds and may protect one player "
            "(themselves included, but not the same player two nights running). "
            "If the wolves' target is protected, nobody dies."
        )
    if rules.lovers_enabled:
        lines.append(
            "  Then the lovers, if both are alive, have a private whisper (see below)."
        )
    return lines


def build_rules(rules: PublicRules) -> str:
    seer_listening = bool(rules.role_counts.get("seer"))
    morning = (
        "the victim's death is announced, or that nobody died."
        if rules.role_counts.get("doctor")
        else "the victim's death is announced."
    )
    lines = [
        (
            "You are playing Werewolf in the sleepy English seaside town of "
            "Tokenbury-on-Sea."
        ),
        "",
        (
            f"Setup: {rules.player_count} players: {_mix(rules.role_counts)}. "
            "Roles are secret."
        ),
        "Each day plays out in this order:",
        *_night_lines(rules),
        f"- Morning: {morning}",
        "- Discussion: everyone alive may speak. Everything said is public.",
        (
            "- Vote: every living player secretly votes for a player, or for no "
            "one. The player with the most votes is eliminated. A tie, or a "
            "majority voting for no one, eliminates nobody."
        ),
        "- Then everyone's day notes are written and the next night begins.",
        (
            "The wolves win when they equal or outnumber everyone else. The town "
            "wins when no wolves remain."
        ),
    ]
    if rules.lovers_enabled:
        lines += [
            "",
            (
                "There may be a pair of secret lovers among the players. If one "
                "of them dies, the other dies of a broken heart at once. Only the "
                "lovers know who they are."
            ),
        ]
    if seer_listening:
        lines += [
            "",
            (
                "Public rules everyone knows: the seer may be listening to the "
                "wolves' night chat, so wolves should assume someone is reading it."
            ),
        ]
    lines += [
        "",
        "General guidance:",
        (
            "- Reason independently. Do not pile onto the first accusation "
            "without evidence."
        ),
        "- Ask questions, answer them, and use your notes to track who said what.",
        (
            "- Your log shows only today. Write down anything you will need "
            "tomorrow: who said what, who you suspect and why, vote results, and "
            "what the dead revealed."
        ),
        "- Wolves may lie. Villagers should expect lies.",
    ]
    return "\n".join(lines)


WOLF_GUIDANCE = (
    "- In wolf chat, do not name yourself or your teammates. Use only the wolf "
    "labels (Wolf A, Wolf B and so on)."
)
SEER_GUIDANCE = (
    "- You cannot speak at night. Work out who the wolves are from how they talk."
)

DOCTOR_GUIDANCE = (
    "- As the doctor, you may protect any living player each night, and you may "
    "protect yourself, but not the same player two nights running. You will be "
    "told if a protection worked."
)
LOVERS_GUIDANCE = (
    "You are secretly in love with {name}. If either of you dies, the other "
    "dies of a broken heart at once. Your partner's role is unknown to you."
)

ROLE_ARTICLES = {
    "wolf": "a wolf",
    "seer": "the seer",
    "doctor": "the doctor",
    "villager": "a villager",
}

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
    "doctor": (
        "It is night and your turn to do your rounds. Choose someone to "
        "protect tonight with protect, or pass."
    ),
    "lovers_chat": (
        "It is night. Have a private word with your partner, or pass if you "
        "have nothing to say."
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
    teammates = tuple((t["name"], t["label"]) for t in info.get("teammates", []))
    if not teammates and info.get("teammate_name"):  # pre-teammates games
        teammates = ((info["teammate_name"], info.get("teammate_label", "")),)
    return PlayerView(
        player_id=player.id,
        name=player.name,
        role=player.role,
        talkativeness=player.character.talkativeness,
        win_condition=info.get("win_condition", ""),
        wolf_label=info.get("wolf_label"),
        teammates=teammates,
        lover_name=info.get("lover_name"),
        lovers_note=info.get("lovers_note"),
    )


def _role_section(view: PlayerView, rules: PublicRules) -> str:
    parts = [
        build_rules(rules),
        "",
        f"Your role: {view.role}.",
        f"Your win condition: {view.win_condition}",
    ]
    if view.role == "wolf":
        mates = [f"{name} ({label})" for name, label in view.teammates]
        if not mates:
            team = "You are the only wolf."
        elif len(mates) == 1:
            team = f"Your teammate is {mates[0]}."
        else:
            team = f"Your teammates are {', '.join(mates[:-1])} and {mates[-1]}."
        parts.append(f"You are {view.wolf_label}. {team}")
        parts.append(WOLF_GUIDANCE)
    elif view.role == "seer":
        parts.append(SEER_GUIDANCE)
    elif view.role == "doctor":
        parts.append(DOCTOR_GUIDANCE)
    if view.lover_name:
        lovers = LOVERS_GUIDANCE.format(name=view.lover_name)
        parts.append(f"{lovers} {view.lovers_note}" if view.lovers_note else lovers)
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
    match p.get("cause"):
        case "night_kill":
            line = f"{p['player']} was killed in the night."
        case "heartbreak":
            line = f"{p['player']} died of a broken heart."
        case _:
            line = f"{p['player']} was eliminated by vote."
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
        case "protect":
            return f"[Night] You protected {p['target']}."
        case "save_result":
            return (
                "Your protection worked: nobody died."
                if p.get("saved")
                else "Your protection did not stop the attack."
            )
        case "peaceful_night":
            return "Nobody died last night."
        case "lover_message":
            return f"[Night, to your love] {event.speaker}: {p['message']}"
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


SPEAKING_KINDS = {"wolf_chat", "lovers_chat", "discussion"}


def build_player_prompt(
    view: PlayerView,
    visible_events: list[VisibleEvent],
    notes: str,
    roster: list[RosterEntry],
    turn: Turn,
    notes_cap: int,
    rules: PublicRules,
    speech_max_chars: int = 400,
) -> list[dict]:
    persona = (
        f"## Who you are\nYou are {view.name}.\n{PERSONA_LINES[view.talkativeness]}"
    )
    roster_text = "## Players\n" + "\n".join(
        _roster_line(e, rules.reveal_role_on_death) for e in roster
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
        + (
            f"Keep what you say to at most {speech_max_chars} characters.\n"
            if turn.kind in SPEAKING_KINDS
            else ""
        )
        + f"Tools you may use: {', '.join(turn.allowed_tools)}.\n"
        "Update your notes before acting if there is anything worth keeping, "
        "then make exactly one action."
    )
    system = "\n\n".join([
        "## Rules and role\n" + _role_section(view, rules),
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
    cfg, counts = game_rules(player.game)
    return build_player_prompt(
        player_view(player),
        events_visible_to(player, day=turn.day),
        current_notes(player),
        build_roster(player),
        turn,
        cfg["notes_max_chars"],
        PublicRules(
            player_count=cfg["player_count"],
            role_counts=counts,
            lovers_enabled=cfg["lovers"],
            reveal_role_on_death=cfg["reveal_role_on_death"],
        ),
        cfg["speech_max_chars"],
    )
