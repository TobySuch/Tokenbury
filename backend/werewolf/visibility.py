"""The only path from game events to agent prompts."""

from dataclasses import dataclass

from werewolf.config import game_config
from werewolf.models import (
    PUBLIC,
    WOLF_CHAT,
    GameEvent,
    Player,
    player_visibility,
)

ID_KEYS = {
    "kill_target_id": "kill_target",
    "target_id": "target",
    "player_id": "player",
    "eliminated_id": "eliminated",
    "voter_id": "voter",
}


@dataclass(frozen=True)
class VisibleEvent:
    seq: int
    day: int
    phase: str
    type: str
    speaker: str | None
    payload: dict


@dataclass(frozen=True)
class RosterEntry:
    name: str
    alive: bool
    role: str | None


def _name(names, pid):
    return None if pid is None else names.get(pid, "Unknown")


def _convert(value, names):
    if isinstance(value, dict):
        return {
            ID_KEYS.get(k, k): (_name(names, v) if k in ID_KEYS else _convert(v, names))
            for k, v in value.items()
            if k != "tally"
        }
    if isinstance(value, list):
        return [_convert(v, names) for v in value]
    return value


def _sanitise(event, names, reveal_role):
    payload = _convert(event.payload, names)
    tally = event.payload.get("tally")
    if isinstance(tally, dict):
        payload["tally"] = {
            ("none" if k == "none" else names.get(int(k), "Unknown")): n
            for k, n in tally.items()
        }
    if event.type == "death" and not reveal_role:
        payload.pop("role", None)
    return payload


def events_visible_to(player, day=None) -> list[VisibleEvent]:
    visibilities = [PUBLIC, player_visibility(player.id)]
    if player.role in (Player.Role.WOLF, Player.Role.SEER):
        visibilities.append(WOLF_CHAT)
    qs = GameEvent.objects.filter(
        game_id=player.game_id, visibility__in=visibilities
    ).order_by("seq")
    if not player.alive:
        death_seq = (
            GameEvent.objects
            .filter(
                game_id=player.game_id,
                type=GameEvent.Type.DEATH,
                payload__player_id=player.id,
            )
            .order_by("seq")
            .values_list("seq", flat=True)
            .first()
        )
        if death_seq is not None:
            qs = qs.filter(seq__lte=death_seq)
    if day is not None:
        qs = qs.filter(day=day)
    events = list(qs)

    players = {
        p.id: p
        for p in Player.objects.filter(game_id=player.game_id).select_related(
            "character", "game"
        )
    }
    names = {pid: p.name for pid, p in players.items()}
    reveal_role = game_config(players[player.id].game)["reveal_role_on_death"]

    visible = []
    for e in events:
        if e.visibility == WOLF_CHAT:
            speaker = players[e.actor_id].wolf_label if e.actor_id else None
        else:
            speaker = names.get(e.actor_id) if e.actor_id else None
        visible.append(
            VisibleEvent(
                seq=e.seq,
                day=e.day,
                phase=e.phase,
                type=e.type,
                speaker=speaker,
                payload=_sanitise(e, names, reveal_role),
            )
        )
        if e.type == "death" and e.payload.get("player_id") == player.id:
            break
    return visible


def build_roster(player) -> list[RosterEntry]:
    """Everyone except the viewer, in seat order. Roles only for the dead
    (and only when reveal_role_on_death is on)."""
    reveal = game_config(player.game)["reveal_role_on_death"]
    others = (
        Player.objects
        .filter(game_id=player.game_id)
        .exclude(pk=player.pk)
        .select_related("character")
        .order_by("seat")
    )
    return [
        RosterEntry(
            name=p.name,
            alive=p.alive,
            role=p.role if (reveal and not p.alive) else None,
        )
        for p in others
    ]


def own_role_info(player) -> dict:
    for e in events_visible_to(player):
        if e.type == "role_assigned":
            return e.payload
    return {}
