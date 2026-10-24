"""Spectator beats: the event log flattened into display steps.

Spectators see everything (true roles, wolf chat), so this never feeds agent
prompts.
"""

from werewolf.models import Game, GameEvent

Phase = Game.Phase

NIGHT_PHASES = {
    Phase.NIGHT_WOLF_CHAT,
    Phase.NIGHT_DOCTOR,
    Phase.NIGHT_LOVERS,
    Phase.NIGHT_SEER,
}

BANNERS = {
    Phase.NIGHT_WOLF_CHAT: "Night {day}",
    Phase.NIGHT_DOCTOR: "Night {day}: The doctor's rounds",
    Phase.NIGHT_LOVERS: "Night {day}: The lovers whisper",
    Phase.NIGHT_SEER: "Night {day}: The seer listens",
    Phase.MORNING: "Day {day}: Morning",
    Phase.DISCUSSION: "Day {day}: Discussion",
    Phase.VOTE: "Day {day}: Vote",
    Phase.ELIMINATION: "Day {day}: Elimination",
    Phase.DAY_NOTES: "Day {day}: Notes",
}


DEATH_BEATS = {
    "night_kill": ("morning", "{name} was killed in the night."),
    "vote": ("elimination", "{name} was eliminated."),
    "heartbreak": ("heartbreak", "{name} died of a broken heart."),
}


def _banner(phase, day):
    template = BANNERS.get(phase)
    return template.format(day=day) if template else ""


def _palette(phase):
    return "night" if phase in NIGHT_PHASES else "day"


def build_beats(game) -> list[dict]:
    players = {p.id: p for p in game.players.all()}
    alive = [p.id for p in sorted(players.values(), key=lambda p: p.seat)]
    events = list(GameEvent.objects.filter(game=game).order_by("seq"))

    state = {"day": 1, "phase": Phase.NIGHT_WOLF_CHAT}
    beats: list[dict] = []

    def add(seq, kind, **fields):
        beats.append({
            "index": len(beats),
            "seq": seq,
            "day": state["day"],
            "phase": state["phase"],
            "kind": kind,
            "palette": _palette(state["phase"]),
            "banner": _banner(state["phase"], state["day"]),
            "actor_id": None,
            "target_id": None,
            "text": None,
            "kill_target_id": None,
            "victim_id": None,
            "role": None,
            "votes": [],
            "tally": {},
            "winner": None,
            "alive_ids": list(alive),
            **fields,
        })

    role_seqs = [e.seq for e in events if e.type == "role_assigned"]
    add(max(role_seqs) if role_seqs else 0, "phase_change")

    for e in events:
        p = e.payload
        if e.type == "phase_change":
            if p["from"] == Phase.DAY_NOTES:
                state["day"] = e.day + 1
            else:
                state["day"] = e.day
            state["phase"] = p["to"]
            add(e.seq, "phase_change")
        elif e.type == "wolf_message":
            add(
                e.seq,
                "wolf_message",
                palette="night",
                actor_id=e.actor_id,
                text=p.get("message"),
                kill_target_id=p.get("kill_target_id"),
            )
        elif e.type == "protect":
            target = players.get(p.get("target_id"))
            add(
                e.seq,
                "protect",
                palette="night",
                actor_id=e.actor_id,
                target_id=p.get("target_id"),
                text=f"The doctor protects {target.name if target else 'someone'}.",
            )
        elif e.type == "lover_message":
            add(
                e.seq,
                "lover_message",
                palette="night",
                actor_id=e.actor_id,
                text=p.get("message"),
            )
        elif e.type == "peaceful_night":
            add(
                e.seq,
                "peaceful_night",
                palette="day",
                text="Nobody died last night.",
            )
        elif e.type == "speech":
            add(e.seq, "speech", actor_id=e.actor_id, text=p.get("message"))
        elif e.type == "death":
            victim = players.get(p["player_id"])
            if victim is None:
                continue
            if victim.id in alive:
                alive.remove(victim.id)
            kind, text = DEATH_BEATS.get(p["cause"], ("morning", "{name} died."))
            add(
                e.seq,
                kind,
                palette="day" if kind == "heartbreak" else _palette(state["phase"]),
                victim_id=victim.id,
                role=victim.role,
                text=text.format(name=victim.name),
            )
        elif e.type == "vote_result":
            eliminated = players.get(p.get("eliminated_id"))
            add(
                e.seq,
                "vote_reveal",
                votes=p.get("votes", []),
                tally=p.get("tally", {}),
                text=(
                    f"{eliminated.name} was voted out."
                    if eliminated
                    else "No one was eliminated."
                ),
            )
        elif e.type == "game_over":
            add(e.seq, "game_over", winner=p.get("winner"))
    return beats
