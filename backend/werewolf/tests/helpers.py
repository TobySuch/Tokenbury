"""Test helpers (not production code)."""

from werewolf.agents import WerewolfAgent
from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, Game
from werewolf.moderator import discussion_state, moderate


def simulate_discussion(game: Game, agent: WerewolfAgent, actions) -> list[dict]:
    """Test helper: run the moderator loop; each picked player does the next
    action ("speech" or "pass", default "speech"). Returns the pick payloads."""
    actions = iter(actions)
    payloads = []
    while True:
        payload = moderate(game, agent, discussion_state(game))
        payloads.append(payload)
        if payload["end"]:
            return payloads
        player = game.players.get(pk=payload["pick_id"])
        if next(actions, "speech") == "pass":
            append_event(
                game,
                type="pass",
                visibility=ENGINE,
                phase=Game.Phase.DISCUSSION,
                actor=player,
                payload={"phase": "discussion"},
            )
        else:
            append_event(
                game,
                type="speech",
                visibility=PUBLIC,
                phase=Game.Phase.DISCUSSION,
                actor=player,
                payload={"message": f"{player.name} speaks"},
            )


def events_of(game, type=None, phase=None, day=None):
    from werewolf.models import GameEvent

    qs = GameEvent.objects.filter(game=game).order_by("seq")
    if type:
        qs = qs.filter(type=type)
    if phase:
        qs = qs.filter(phase=phase)
    if day:
        qs = qs.filter(day=day)
    return list(qs)


ID_KEYS = {"target_id", "kill_target_id", "player_id", "eliminated_id", "voter_id"}


def normalised_log(game):
    """The event log with player ids replaced by seats, for cross-game comparison."""
    from werewolf.models import GameEvent

    seats = {p.id: p.seat for p in game.players.all()}

    def conv(value):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if k in ID_KEYS or k == "pick_id":
                    out[k] = seats.get(v) if v is not None else None
                elif k == "tally":
                    out[k] = {
                        ("none" if t == "none" else seats[int(t)]): n
                        for t, n in v.items()
                    }
                else:
                    out[k] = conv(v)
            return out
        if isinstance(value, list):
            return [conv(v) for v in value]
        return value

    return [
        (
            e.seq,
            e.day,
            e.phase,
            e.type,
            e.visibility
            if not e.visibility.startswith("player:")
            else f"player:{seats[int(e.visibility.split(':')[1])]}",
            seats.get(e.actor_id),
            conv(e.payload),
        )
        for e in GameEvent.objects.filter(game=game).order_by("seq")
    ]


class CapturingProvider:
    """Wraps a provider, recording every prompt with the game state at that moment."""

    def __init__(self, inner):
        self.inner = inner
        self.player_prompts = []  # dicts: player_id, text, max_seq, day
        self.moderator_prompts = []  # str

    def _wrap(self, agent, player):
        from django.db.models import Max

        from werewolf.agents import ScriptedAgent
        from werewolf.models import Game, GameEvent

        capture = self

        class Wrapped(ScriptedAgent):
            def __init__(self):
                pass

            def respond(self, messages, tools):
                text = "\n".join(m["content"] for m in messages if m.get("content"))
                if player is None:
                    capture.moderator_prompts.append(text)
                else:
                    game = Game.objects.get(pk=player.game_id)
                    capture.player_prompts.append({
                        "player_id": player.id,
                        "text": text,
                        "max_seq": GameEvent.objects.filter(game=game).aggregate(
                            m=Max("seq")
                        )["m"],
                        "day": game.day_number,
                    })
                return agent.respond(messages, tools)

        return Wrapped()

    def player_agent(self, player):
        return self._wrap(self.inner.player_agent(player), player)

    def moderator_agent(self):
        return self._wrap(self.inner.moderator_agent(), None)
