"""Prompt assembly. ``build_player_prompt`` is pure and takes no Game/Player;
``build_prompt_for`` is the DB-touching pipeline the engine uses."""

from dataclasses import dataclass, field

from werewolf.config import game_rules
from werewolf.notes import current_notes
from werewolf.rng import rng_for
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


def _facts(rules: PublicRules) -> list[str]:
    """How every role and announcement works. Public knowledge, so players can
    reason from it (and don't treat a certain deduction as a wild guess)."""
    has_seer = bool(rules.role_counts.get("seer"))
    has_doctor = bool(rules.role_counts.get("doctor"))
    facts = [
        (
            "- Every death is announced to everyone with its cause: killed in the "
            "night by the wolves, eliminated by the vote"
            + (", or died of a broken heart." if rules.lovers_enabled else ".")
        ),
    ]
    if rules.reveal_role_on_death:
        facts.append(
            "- When a player dies, their role is revealed to everyone"
            + (
                ", and so is their lover if they had one."
                if rules.lovers_enabled
                else "."
            )
        )
    else:
        facts.append("- Roles are not revealed when players die.")
    if rules.lovers_enabled:
        facts.append(
            "- A death by broken heart only happens when that player's lover has "
            "just died. So the player who died of a broken heart and the player "
            "who died just before them were the lovers: that is certain, not a "
            "guess."
        )
    if has_doctor:
        facts.append(
            '- "Nobody died last night" means the doctor protected the wolves\' '
            "target. Only the doctor is told whether their protection worked; "
            "nobody is told who was protected."
        )
    if has_seer:
        facts.append(
            "- The seer only sees the wolves' chat, with the speakers shown as "
            "wolf labels, never names."
        )
    facts.append(
        "- Nobody can investigate or check another player's role. The wolves "
        "know who the other wolves are"
        + (
            ", and the lovers know who their partner is but not their partner's role."
            if rules.lovers_enabled
            else "."
        )
        + " Nobody else knows anyone's role."
    )
    private = ["the wolves' chat"]
    if rules.lovers_enabled:
        private.append("the lovers' whisper")
    facts.append(
        f"- {' and '.join(private).capitalize()} "
        + ("are" if len(private) > 1 else "is")
        + " private: nobody else hears "
        + ("them" if len(private) > 1 else "it")
        + (" (except the seer, who reads the wolves' chat)." if has_seer else ".")
    )
    return ["## How everything works (everyone knows this)", *facts]


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
    lines += ["", *_facts(rules)]
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
        (
            "- Never invent events or impressions. Use only what is in your log "
            "and notes. On the first night nobody has spoken yet, so there is "
            "nothing to go on: any first-night choice is a guess."
        ),
        (
            "- Voting for no one is fine when there is nothing to go on, but the "
            "wolves kill every night, so the town cannot wait for ever."
        ),
        (
            "- Think before revealing your role. Anyone who announces a special "
            "role is likely to be the wolves' next target."
        ),
        (
            "- Do not start your messages with your own name; everyone can "
            "already see who is speaking."
        ),
    ]
    return "\n".join(lines)


ABILITIES = {
    "wolf": (
        "- At night you talk privately with the other wolves and propose a kill "
        "target (kill_target). The kill happens when every living wolf names the "
        "same target; otherwise one of the named targets is picked at random.\n"
        "- In wolf chat, do not name yourself or your teammates. Use only the wolf "
        "labels (Wolf A, Wolf B and so on). The seer may be reading.\n"
        "- By day you speak and vote like everyone else. Nobody else knows you are "
        "a wolf, so you will need to blend in and lie convincingly.\n"
        "- You cannot see anyone else's role."
    ),
    "seer": (
        "- At night you automatically see the wolves' private chat in your log, "
        "with the speakers shown only as wolf labels. That is your only night "
        "ability: you have no power to investigate or check anyone, and you "
        "cannot speak or act at night.\n"
        "- Work out who the wolves are from how they talk, and keep careful notes.\n"
        "- By day you speak and vote like everyone else. If you reveal you are "
        "the seer, the wolves will probably kill you next."
    ),
    "doctor": (
        "- Each night you may protect one living player, yourself included, but "
        "not the same player two nights running. If the wolves attack that "
        "player, nobody dies. You may also pass.\n"
        "- The next morning you are told privately whether your protection "
        "stopped an attack.\n"
        "- You do not see the wolf chat and cannot investigate anyone.\n"
        "- By day you speak and vote like everyone else. If you reveal you are "
        "the doctor, the wolves may kill you next."
    ),
    "villager": (
        "- You have no night action: you sleep through the night.\n"
        "- By day you speak and vote. Your power is your reasoning and your vote."
    ),
}
LOVER_ABILITY = (
    "- Each night you and {name} may whisper privately. Your partner may be on "
    "the other side: anything you tell them, they could use against you or your "
    "team. Think carefully before passing on anything you learned at night."
)
ABILITIES_FOOTER = (
    "These are all your abilities. You have no other powers, tools or checks."
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
        "It is night. Talk privately with your fellow wolves. Propose a kill "
        "target with kill_target (a living non-wolf); the chat ends early once "
        "every living wolf names the same one."
    ),
    "seer_notes": (
        "It is night. Tonight's wolf chat is in your log above. You have no "
        "other night action and cannot speak. Record what you noticed in your "
        "notes, then pass."
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
    if view.lover_name:
        lovers = LOVERS_GUIDANCE.format(name=view.lover_name)
        parts.append(f"{lovers} {view.lovers_note}" if view.lovers_note else lovers)
    return "\n".join(parts)


def _abilities_section(view: PlayerView) -> str:
    lines = [ABILITIES.get(view.role, ABILITIES["villager"])]
    if view.lover_name:
        lines.append(LOVER_ABILITY.format(name=view.lover_name))
    lines.append(ABILITIES_FOOTER)
    return "## Your abilities\n" + "\n".join(lines)


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
    if p.get("lover"):
        line += f" Their lover was {p['lover']}."
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


CAUSE_PHRASES = {
    "night_kill": "killed in the night",
    "vote": "eliminated by vote",
    "heartbreak": "died of a broken heart",
}


def _roster_line(entry: RosterEntry, reveal: bool) -> str:
    if entry.alive:
        return f"- {entry.name} (alive)"
    details = []
    if entry.cause:
        how = CAUSE_PHRASES.get(entry.cause, "died")
        details.append(f"{how} on day {entry.died_day}" if entry.died_day else how)
    if reveal and entry.role:
        details.append(f"was {_article(entry.role)}")
    if reveal and entry.lover:
        details.append(f"{entry.lover}'s lover")
    return (
        f"- {entry.name} (dead: {'; '.join(details)})"
        if details
        else f"- {entry.name} (dead)"
    )


SPEAKING_KINDS = {"wolf_chat", "lovers_chat", "discussion"}

AUDIENCE = {
    "discussion": "Who hears this: everyone, including the wolves.",
    "wolf_chat": (
        "Who hears this: your fellow wolves, and the seer may be reading (they "
        "see wolf labels, not names)."
    ),
    "lovers_chat": (
        "Who hears this: only your partner. They may be on the other side, so "
        "be careful what you reveal."
    ),
}
SPEECH_RULE = (
    "Write only the words you say to them: no narration or stage directions. "
    "Your private reasoning belongs in your notes, not in what you say."
)


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
            f"{AUDIENCE[turn.kind]}\n{SPEECH_RULE}\n"
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
        _abilities_section(view),
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
    # Seat order would put the same player first in every roster, and models
    # favour the first name they see (e.g. for the first night's kill). Shuffle
    # per player and per day: replayable, and stable within a day for caching.
    roster = build_roster(player)
    rng_for(player.game, "roster", str(player.id), str(turn.day)).shuffle(roster)
    return build_player_prompt(
        player_view(player),
        events_visible_to(player, day=turn.day),
        current_notes(player),
        roster,
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
