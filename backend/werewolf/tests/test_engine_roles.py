"""Engine behaviour for the doctor, the lovers and larger games."""

import pytest

from werewolf.engine import (
    ScriptedProvider,
    _check_win,
    run_day,
    validation_context,
)
from werewolf.models import AgentCall, Character, Game, Player
from werewolf.setup import create_game
from werewolf.tests.factories import make_characters
from werewolf.tests.helpers import events_of

pytestmark = pytest.mark.django_db


def new_game(seed=5, **config):
    if not Character.objects.exists():
        make_characters(12)
    return create_game(seed=seed, config=config)


def by_role(game, role):
    return list(game.players.filter(role=role).order_by("seat"))


def link(a, b):
    """Make a and b the (only) lovers."""
    Player.objects.filter(game=a.game).update(lover=None)
    Player.objects.filter(pk=a.pk).update(lover=b)
    Player.objects.filter(pk=b.pk).update(lover=a)


def kill(*players):
    Player.objects.filter(pk__in=[p.pk for p in players]).update(alive=False)


def fresh(game):
    game.refresh_from_db()
    return game


class Cast(ScriptedProvider):
    """Scripted policy with the night decisions fixed by the test."""

    def __init__(
        self,
        game,
        kill=None,
        protects=None,
        lover_actions=None,
        wolf_targets=None,
        votes=None,
    ):
        super().__init__(game)
        self.kill = kill
        self.protects = protects or {}  # day -> Player | None (pass)
        self.lover_actions = list(lover_actions or [])  # "speak" | "pass"
        self.wolf_targets = wolf_targets or {}  # wolf seat -> Player
        self.votes = votes or {}  # voter seat -> target seat | None

    def wolf_step(self, player, day, n):
        target = self.wolf_targets.get(player.seat, self.kill)
        args = {"message": f"[{player.wolf_label} d{day} #{n}] go"}
        if target is not None:
            args["kill_target"] = target.name
        return [("speak", args)]

    def doctor_step(self, player, day, n):
        target = self.protects.get(day)
        if target is None:
            return [("pass", {})]
        return [("protect", {"target": target.name})]

    def lovers_step(self, player, day, n):
        action = self.lover_actions.pop(0) if self.lover_actions else "speak"
        if action == "pass":
            return [("pass", {})]
        return [("speak", {"message": f"[{player.name} d{day} #{n} love] hi"})]

    def vote_step(self, player, day, n):
        if player.seat not in self.votes:
            return [("vote", {"target": "none"})]
        target = self.votes[player.seat]
        name = "none" if target is None else self.game.players.get(seat=target).name
        return [("vote", {"target": name})]


def villagers_not_wolf(game):
    return [p for p in game.players.order_by("seat") if p.role != "wolf"]


def deaths(game):
    return [
        (e.payload["cause"], e.payload["player_id"])
        for e in events_of(game, type="death")
    ]


# ------------------------------------------------------------- doctor


def test_doctor_saves_the_target():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    victim = by_role(game, "villager")[0]
    run_day(game, Cast(game, kill=victim, protects={1: victim}))
    game = fresh(game)
    assert Player.objects.get(pk=victim.pk).alive
    assert [d for d in deaths(game) if d[0] == "night_kill"] == []
    (peace,) = events_of(game, type="peaceful_night")
    assert peace.visibility == "public" and peace.payload == {}
    (protect,) = events_of(game, type="protect")
    assert protect.actor_id == doctor.id and protect.phase == "night_doctor"
    assert protect.payload == {"target_id": victim.id}
    assert protect.visibility == f"player:{doctor.id}"
    (save,) = events_of(game, type="save_result")
    assert save.payload == {"saved": True}
    assert save.visibility == f"player:{doctor.id}" and save.actor is None
    assert game.day_number == 2


def test_failed_protection_reports_false_and_victim_dies():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    villagers = by_role(game, "villager")
    run_day(game, Cast(game, kill=villagers[0], protects={1: villagers[1]}))
    game = fresh(game)
    assert not Player.objects.get(pk=villagers[0].pk).alive
    assert events_of(game, type="peaceful_night") == []
    (save,) = events_of(game, type="save_result")
    assert save.payload == {"saved": False}
    assert save.visibility == f"player:{doctor.id}"


def test_doctor_pass_writes_no_save_result():
    game = new_game()
    victim = by_role(game, "villager")[0]
    run_day(game, Cast(game, kill=victim))
    game = fresh(game)
    assert events_of(game, type="protect") == []
    assert events_of(game, type="save_result") == []
    assert not Player.objects.get(pk=victim.pk).alive
    passes = events_of(game, type="pass", phase="night_doctor")
    assert len(passes) == 1 and passes[0].visibility == "engine"


def test_doctor_cannot_protect_same_player_two_nights_running():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    seer = by_role(game, "seer")[0]
    villager = by_role(game, "villager")[0]
    provider = Cast(game, kill=villager, protects={1: seer, 2: seer})
    run_day(game, provider)
    run_day(game, provider)
    game = fresh(game)
    day1 = events_of(game, type="protect", day=1)
    assert [e.payload["target_id"] for e in day1] == [seer.id]
    assert events_of(game, type="protect", day=2) == []
    passes = events_of(game, type="pass", phase="night_doctor", day=2)
    assert [e.actor_id for e in passes] == [doctor.id]
    assert AgentCall.objects.filter(player=doctor).count() >= 2 + 3


def test_validation_context_last_protected_and_lover_flag():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    seer = by_role(game, "seer")[0]
    villager = by_role(game, "villager")[0]
    link(villager, seer)
    assert validation_context(game, doctor, "doctor").last_protected is None
    run_day(game, Cast(game, kill=by_role(game, "villager")[1], protects={1: seer}))
    game = fresh(game)
    ctx = validation_context(game, Player.objects.get(pk=doctor.pk), "doctor")
    assert ctx.last_protected == seer.name
    assert validation_context(game, villager, "lovers_chat").actor_is_lover
    assert not validation_context(game, doctor, "doctor").actor_is_lover


def test_last_protected_clears_after_a_pass():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    seer = by_role(game, "seer")[0]
    provider = Cast(game, kill=by_role(game, "villager")[0], protects={1: seer})
    run_day(game, provider)
    provider.protects = {}
    run_day(game, provider)  # passes on day 2
    game = fresh(game)
    ctx = validation_context(game, Player.objects.get(pk=doctor.pk), "doctor")
    assert ctx.last_protected is None


def test_dead_doctor_gets_no_turn_but_phase_still_passes():
    game = new_game()
    doctor = by_role(game, "doctor")[0]
    kill(doctor)
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    game = fresh(game)
    assert AgentCall.objects.filter(player=doctor).count() == 0
    assert events_of(game, phase="night_doctor", type="pass") == []
    assert ("night_doctor", "night_lovers") in [
        (e.payload["from"], e.payload["to"])
        for e in events_of(game, type="phase_change")
    ]


def test_phase_order_with_doctor_and_lovers():
    game = new_game()
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    changes = [
        (e.payload["from"], e.payload["to"])
        for e in events_of(fresh(game), type="phase_change")
    ]
    assert changes[:5] == [
        ("night_wolf_chat", "night_doctor"),
        ("night_doctor", "night_lovers"),
        ("night_lovers", "night_seer"),
        ("night_seer", "morning"),
        ("morning", "discussion"),
    ]


# ------------------------------------------------------------- lovers


def lover_pair(game):
    return sorted(game.players.filter(lover__isnull=False), key=lambda p: p.seat)


def test_lovers_chat_alternates_up_to_the_cap():
    game = new_game()
    a, b = lover_pair(game)
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    msgs = events_of(fresh(game), type="lover_message")
    assert len(msgs) == 4
    assert [m.actor_id for m in msgs] == [a.id, b.id, a.id, b.id]
    assert {m.visibility for m in msgs} == {"lovers"}
    assert {m.phase for m in msgs} == {"night_lovers"}


def test_lovers_chat_respects_configured_cap():
    game = new_game(lovers_chat_max_messages=3)
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    assert len(events_of(fresh(game), type="lover_message")) == 3


def test_lovers_chat_ends_early_after_two_consecutive_passes():
    game = new_game()
    a, b = lover_pair(game)
    run_day(
        game,
        Cast(
            game,
            kill=by_role(game, "villager")[0],
            lover_actions=["speak", "pass", "pass", "speak"],
        ),
    )
    game = fresh(game)
    assert len(events_of(game, type="lover_message")) == 1
    passes = events_of(game, type="pass", phase="night_lovers")
    assert [p.actor_id for p in passes] == [b.id, a.id]


def test_lovers_chat_passes_not_consecutive_do_not_end_early():
    game = new_game()
    run_day(
        game,
        Cast(
            game,
            kill=by_role(game, "villager")[0],
            lover_actions=["pass", "speak", "pass", "speak"],
        ),
    )
    game = fresh(game)
    assert len(events_of(game, type="lover_message")) == 2
    assert len(events_of(game, type="pass", phase="night_lovers")) == 2


def test_lovers_chat_skipped_when_a_lover_is_dead():
    game = new_game()
    a, b = lover_pair(game)
    kill(a)
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    game = fresh(game)
    assert events_of(game, phase="night_lovers", type="lover_message") == []
    assert events_of(game, phase="night_lovers", type="pass") == []
    assert not any("love" in c.response for c in AgentCall.objects.filter(player=b))


def test_lovers_chat_skipped_when_lovers_are_off():
    game = new_game(lovers=False)
    run_day(game, Cast(game, kill=by_role(game, "villager")[0]))
    game = fresh(game)
    assert events_of(game, type="lover_message") == []
    assert [
        e for e in events_of(game, phase="night_lovers") if e.type != "phase_change"
    ] == []
    assert game.day_number == 2


# --------------------------------------------------------- heartbreak


def two_villagers(game):
    villagers = by_role(game, "villager")
    link(villagers[0], villagers[1])
    return villagers[0], villagers[1]


def test_heartbreak_after_night_kill():
    game = new_game()
    a, b = two_villagers(game)
    run_day(game, Cast(game, kill=a))
    game = fresh(game)
    assert deaths(game) == [("night_kill", a.id), ("heartbreak", b.id)]
    death = events_of(game, type="death")[1]
    assert death.visibility == "public" and death.payload["role"] == "villager"
    assert not Player.objects.get(pk=b.pk).alive
    assert game.status == "active"


def test_heartbreak_hides_role_when_reveal_is_off():
    game = new_game(reveal_role_on_death=False)
    a, _b = two_villagers(game)
    run_day(game, Cast(game, kill=a))
    deaths_ = events_of(fresh(game), type="death")
    assert [d.payload["cause"] for d in deaths_] == ["night_kill", "heartbreak"]
    assert all(d.payload["role"] is None for d in deaths_)


def test_heartbreak_after_vote():
    game = new_game(player_count=10)
    a, b = two_villagers(game)
    other = by_role(game, "villager")[2]
    living = [p for p in game.players.order_by("seat") if p.pk != other.pk]
    votes = {p.seat: (None if p.pk == a.pk else a.seat) for p in living}
    run_day(game, Cast(game, kill=other, votes=votes))
    game = fresh(game)
    assert deaths(game) == [
        ("night_kill", other.id),
        ("vote", a.id),
        ("heartbreak", b.id),
    ]
    assert events_of(game, type="death")[2].payload["role"] == "villager"
    assert fresh(game).status == "active"


def test_heartbreak_can_end_the_game():
    game = new_game()
    a, b = two_villagers(game)
    villagers = by_role(game, "villager")
    kill(villagers[2])  # 2 wolves vs seer, doctor, a, b
    run_day(game, Cast(game, kill=a))
    game = fresh(game)
    assert game.status == "finished" and game.winner == "wolves"
    assert deaths(game)[-1] == ("heartbreak", b.id)
    assert events_of(game, type="speech") == []
    assert events_of(game, type="game_over")[0].phase == "morning"


def test_heartbreak_is_not_duplicated_when_morning_reruns():
    from werewolf.engine import _kill

    game = new_game()
    a, b = two_villagers(game)
    _kill(game, a.id, "night_kill")
    assert len(events_of(game, type="death")) == 2
    assert not Player.objects.get(pk=b.pk).alive


# ------------------------------------------------------------ win checks


def alone_with(game, *keep):
    kill(*[p for p in game.players.all() if p.pk not in {k.pk for k in keep}])


def test_mixed_lovers_last_two_win_together():
    game = new_game()
    wolf = by_role(game, "wolf")[0]
    villager = by_role(game, "villager")[0]
    extra = by_role(game, "villager")[1]
    link(wolf, villager)
    alone_with(game, wolf, villager, extra)
    run_day(game, Cast(game, kill=extra))
    game = fresh(game)
    assert game.status == "finished" and game.winner == "lovers"
    assert events_of(game, type="game_over")[0].payload == {"winner": "lovers"}


def test_same_team_lovers_do_not_trigger_the_lovers_win():
    game = new_game()
    a, b = two_villagers(game)
    alone_with(game, a, b)
    assert _check_win(game)
    assert fresh(game).winner == "town"


def test_unlinked_last_two_wolf_and_villager_is_a_wolf_win():
    game = new_game()
    wolf = by_role(game, "wolf")[0]
    villager = by_role(game, "villager")[0]
    link(by_role(game, "villager")[1], by_role(game, "villager")[2])
    alone_with(game, wolf, villager)
    assert _check_win(game)
    assert fresh(game).winner == "wolves"


def test_mixed_lovers_with_a_third_alive_is_not_a_win():
    game = new_game()
    wolf = by_role(game, "wolf")[0]
    villagers = by_role(game, "villager")
    link(wolf, villagers[0])
    alone_with(game, wolf, villagers[0], villagers[1], villagers[2])
    assert not _check_win(game)


# ------------------------------------------------------------ N wolves


def test_three_wolf_chat_rotates_and_caps():
    game = new_game(seed=3, player_count=9)
    wolves = by_role(game, "wolf")
    assert len(wolves) == 3
    others = [p for p in villagers_not_wolf(game)]
    run_day(
        game,
        Cast(
            game,
            wolf_targets={w.seat: others[i] for i, w in enumerate(wolves)},
        ),
    )
    msgs = events_of(game, type="wolf_message")
    assert [m.actor_id for m in msgs] == [w.id for w in wolves] * 2
    assert events_of(game, type="wolf_target")[0].payload["source"] == "engine_random"


def test_three_wolf_chat_needs_every_wolf_to_agree():
    game = new_game(seed=3, player_count=9)
    wolves = by_role(game, "wolf")
    others = villagers_not_wolf(game)
    victim = others[0]
    run_day(
        game,
        Cast(
            game,
            kill=victim,
            wolf_targets={wolves[2].seat: others[1]},
        ),
    )
    # Wolf C never agrees, so the chat runs to the cap.
    assert len(events_of(game, type="wolf_message")) == 6


def test_three_wolf_chat_ends_when_all_agree():
    game = new_game(seed=3, player_count=9)
    victim = villagers_not_wolf(game)[0]
    run_day(game, Cast(game, kill=victim))
    assert len(events_of(game, type="wolf_message")) == 3
    (target,) = events_of(game, type="wolf_target")
    assert target.payload == {"target_id": victim.id, "source": "agreed"}


# ------------------------------------------------------- player counts


def test_five_player_game_has_no_doctor_turns():
    game = new_game(player_count=5)
    assert not game.players.filter(role="doctor").exists()
    run_day(game, ScriptedProvider(game))
    game = fresh(game)
    assert events_of(game, type="protect") == []
    assert events_of(game, phase="night_doctor", type="pass") == []


def test_twelve_player_game_plays_a_day():
    game = new_game(player_count=12)
    assert game.players.filter(role="wolf").count() == 3
    run_day(game, ScriptedProvider(game))
    assert fresh(game).day_number >= 2 or fresh(game).status == "finished"


@pytest.mark.parametrize("players", range(5, 13))
@pytest.mark.parametrize("seed", [1, 2])
def test_full_default_games_finish_with_a_winner(players, seed):
    game = new_game(seed=seed, player_count=players)
    provider = ScriptedProvider(game)
    for _ in range(12):
        game = fresh(game)
        if game.status != Game.Status.ACTIVE:
            break
        run_day(game, provider)
    game = fresh(game)
    assert game.status == "finished"
    assert game.winner in {"wolves", "town", "lovers", "draw"}
