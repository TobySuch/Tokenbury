import pytest

from simulation.llm import LLMError
from werewolf.agents import LLMAgent
from werewolf.engine import (
    LLMProvider,
    ScriptedProvider,
    run_day,
    validation_context,
)
from werewolf.models import AgentCall, Character, Game, GameEvent, Player
from werewolf.setup import create_game
from werewolf.tests.factories import make_characters
from werewolf.tests.helpers import events_of

pytestmark = pytest.mark.django_db


def new_game(seed=5, config=None):
    if not Character.objects.exists():
        make_characters(7)
    return create_game(seed=seed, config=config)


def by_role(game, role):
    return list(game.players.filter(role=role).order_by("seat"))


def non_wolves(game):
    return [p for p in game.players.order_by("seat") if p.role != "wolf"]


def kill(*players):
    Player.objects.filter(pk__in=[p.pk for p in players]).update(alive=False)


class Controlled(ScriptedProvider):
    """Scripted policy with the interesting decisions fixed by the test."""

    def __init__(self, game, kill=None, votes=None, wolf_targets=None):
        super().__init__(game)
        self.kill = kill
        self.votes = votes or {}
        self.wolf_targets = wolf_targets or {}  # wolf seat -> player | None

    def wolf_step(self, player, day, n):
        if player.seat in self.wolf_targets:
            target = self.wolf_targets[player.seat]
        else:
            target = self.kill
        args = {"message": f"[{player.wolf_label} d{day} #{n}] go"}
        if target is not None:
            args["kill_target"] = target.name
        return [("speak", args)]

    def vote_step(self, player, day, n):
        if player.seat not in self.votes:
            return [("vote", {"target": "none"})]
        target = self.votes[player.seat]
        name = "none" if target is None else self.game.players.get(seat=target).name
        return [("vote", {"target": name})]


def fresh(game):
    game.refresh_from_db()
    return game


def death_events(game):
    return events_of(game, type="death")


# ---------------------------------------------------------------- helpers


def test_validation_context_fields():
    game = new_game()
    wolf = by_role(game, "wolf")[0]
    villager = by_role(game, "villager")[0]
    kill(villager)
    ctx = validation_context(game, wolf, "wolf_chat")
    assert ctx.turn_kind == "wolf_chat"
    assert ctx.actor_name == wolf.name
    assert ctx.actor_role == "wolf" and ctx.actor_alive
    assert set(ctx.wolf_names) == {w.name for w in by_role(game, "wolf")}
    assert villager.name not in ctx.living_names
    assert len(ctx.living_names) == 6
    assert set(ctx.living_non_wolf_names) == {
        p.name for p in non_wolves(game) if p.alive
    }
    assert ctx.speech_max_chars == 400


def test_llm_provider_uses_config_timeout():
    game = new_game(config={"call_timeout_seconds": 17})
    provider = LLMProvider(game)
    agent = provider.player_agent(game.players.first())
    assert isinstance(agent, LLMAgent) and agent.timeout == 17
    assert isinstance(provider.moderator_agent(), LLMAgent)


def test_run_day_noop_when_not_active():
    game = new_game()
    game.status = Game.Status.FINISHED
    game.save()
    before = GameEvent.objects.count()
    run_day(game, Controlled(game))
    assert GameEvent.objects.count() == before
    assert AgentCall.objects.count() == 0


# ------------------------------------------------------------- day flow


def test_full_day_runs_to_next_night():
    game = new_game()
    wolf = by_role(game, "wolf")[0]
    victim = non_wolves(game)[0]
    run_day(game, Controlled(game, kill=victim))
    game = fresh(game)
    assert game.status == "active"
    assert game.day_number == 2 and game.phase == "night_wolf_chat"
    (death,) = [e for e in death_events(game) if e.payload["cause"] == "night_kill"]
    assert death.payload["player_id"] == victim.id
    assert death.payload["role"] == victim.role
    assert death.visibility == "public"
    assert not Player.objects.get(pk=victim.pk).alive
    assert Player.objects.get(pk=wolf.pk).alive
    changes = [
        (e.payload["from"], e.payload["to"])
        for e in events_of(game, type="phase_change")
    ]
    assert changes == [
        ("night_wolf_chat", "night_seer"),
        ("night_seer", "morning"),
        ("morning", "discussion"),
        ("discussion", "vote"),
        ("vote", "elimination"),
        ("elimination", "day_notes"),
        ("day_notes", "night_wolf_chat"),
    ]
    assert {e.visibility for e in events_of(game, type="phase_change")} == {"engine"}
    seqs = [e.seq for e in events_of(game)]
    assert seqs == list(range(1, len(seqs) + 1))


def test_night_kill_that_ends_the_game_skips_discussion():
    game = new_game()
    others = non_wolves(game)
    kill(others[0], others[1], others[2])  # 2 wolves vs 2 others
    run_day(game, Controlled(game, kill=others[3]))
    game = fresh(game)
    assert game.status == "finished" and game.phase == "game_over"
    assert game.winner == "wolves"
    assert events_of(game, type="speech") == []
    (over,) = events_of(game, type="game_over")
    assert over.payload == {"winner": "wolves"} and over.visibility == "public"


def living_after_night(game, victim):
    return [p for p in game.players.order_by("seat") if p.pk != victim.pk and p.alive]


def vote_plan(living, spec):
    """spec: list indexed like ``living``: index of target or None."""
    return {
        living[i].seat: (None if t is None else living[t].seat)
        for i, t in enumerate(spec)
    }


def run_vote_case(spec, config=None, pre_dead=()):
    game = new_game(config=config)
    victim = by_role(game, "villager")[0]
    kill(*pre_dead)
    living = living_after_night(game, victim)
    run_day(game, Controlled(game, kill=victim, votes=vote_plan(living, spec)))
    return fresh(game), living


def vote_result(game):
    (result,) = events_of(game, type="vote_result")
    return result


def test_tied_vote_eliminates_nobody():
    game, living = run_vote_case([2, 2, 0, 0, None, None])
    result = vote_result(game)
    assert result.payload["eliminated_id"] is None
    assert [e for e in death_events(game) if e.payload["cause"] == "vote"] == []
    assert result.payload["tally"] == {
        str(living[2].id): 2,
        str(living[0].id): 2,
        "none": 2,
    }


def test_strict_majority_for_none_eliminates_nobody():
    game, _ = run_vote_case([None, None, None, None, 0, 0])  # 4 of 6 none
    assert vote_result(game).payload["eliminated_id"] is None


def test_plurality_with_some_none_votes_eliminates():
    # 3 for l0, 3 none: none is not a strict majority of 6.
    game, living = run_vote_case([None, 0, 0, 0, None, None])
    result = vote_result(game)
    assert result.payload["eliminated_id"] == living[0].id
    (death,) = [e for e in death_events(game) if e.payload["cause"] == "vote"]
    assert death.payload["player_id"] == living[0].id
    assert not Player.objects.get(pk=living[0].pk).alive


def test_all_none_votes_eliminates_nobody():
    game, _ = run_vote_case([None] * 6)
    assert vote_result(game).payload["eliminated_id"] is None


def test_votes_list_in_result_when_public():
    game, living = run_vote_case([1, 0, 0, 0, 0, 0])
    votes = vote_result(game).payload["votes"]
    assert len(votes) == 6
    assert {"voter_id": living[0].id, "target_id": living[1].id} in votes
    assert vote_result(game).visibility == "public"
    casts = events_of(game, type="vote_cast")
    assert len(casts) == 6 and {c.visibility for c in casts} == {"engine"}


def test_votes_hidden_when_votes_public_off():
    game, _ = run_vote_case([1, 0, 0, 0, 0, 0], config={"votes_public": False})
    assert vote_result(game).payload["votes"] == []
    assert sum(vote_result(game).payload["tally"].values()) == 6


def test_role_hidden_in_death_when_reveal_off():
    game, _ = run_vote_case(
        [None, 0, 0, 0, None, None], config={"reveal_role_on_death": False}
    )
    deaths = death_events(game)
    assert len(deaths) == 2
    assert all(d.payload["role"] is None for d in deaths)


def test_wolves_reach_parity_after_elimination():
    game = new_game()
    villagers = by_role(game, "villager")
    kill(villagers[0])  # 2 wolves, seer, 3 villagers alive
    victim = villagers[1]
    living = living_after_night(game, victim)  # 2 wolves vs 3 others
    target = next(i for i, p in enumerate(living) if p.role == "villager")
    spec = [target] * 5
    spec[target] = None
    run_day(game, Controlled(game, kill=victim, votes=vote_plan(living, spec)))
    game = fresh(game)
    assert game.status == "finished" and game.winner == "wolves"
    assert events_of(game, type="game_over")[0].phase == "elimination"
    assert events_of(game, type="notes_turn_done", phase="day_notes") == []


def test_last_wolf_eliminated_town_wins():
    game = new_game()
    wolves = by_role(game, "wolf")
    kill(wolves[1])
    victim = by_role(game, "villager")[0]
    living = living_after_night(game, victim)
    wolf_idx = next(i for i, p in enumerate(living) if p.role == "wolf")
    spec = [wolf_idx] * len(living)
    spec[wolf_idx] = None
    run_day(game, Controlled(game, kill=victim, votes=vote_plan(living, spec)))
    game = fresh(game)
    assert game.status == "finished" and game.winner == "town"
    assert game.phase == "game_over"


def test_max_days_draw():
    game = new_game(config={"max_days": 1})
    run_day(game, Controlled(game, kill=non_wolves(game)[0]))
    game = fresh(game)
    assert game.status == "finished" and game.winner == "draw"
    assert game.phase == "game_over"
    assert events_of(game, type="game_over")[0].payload == {"winner": "draw"}


# ------------------------------------------------------------ wolf chat


def wolf_msgs(game):
    return events_of(game, type="wolf_message")


def test_wolf_chat_ends_early_on_agreement():
    game = new_game()
    victim = non_wolves(game)[1]
    run_day(game, Controlled(game, kill=victim))
    msgs = wolf_msgs(game)
    assert len(msgs) == 2
    (target,) = events_of(game, type="wolf_target")
    assert target.payload == {"target_id": victim.id, "source": "agreed"}
    assert target.visibility == "wolf_chat" and target.actor is None
    assert msgs[0].visibility == "wolf_chat"
    assert msgs[0].payload["kill_target_id"] == victim.id


def test_wolf_chat_alternates_wolves_in_seat_order():
    game = new_game()
    a, b = by_role(game, "wolf")
    others = non_wolves(game)
    run_day(
        game,
        Controlled(game, wolf_targets={a.seat: others[0], b.seat: others[1]}),
    )
    actors = [e.actor_id for e in wolf_msgs(game)]
    assert actors == [a.id, b.id] * 3


def test_wolf_chat_cap_picks_among_named_targets():
    game = new_game()
    a, b = by_role(game, "wolf")
    others = non_wolves(game)
    run_day(
        game,
        Controlled(game, wolf_targets={a.seat: others[0], b.seat: others[1]}),
    )
    assert len(wolf_msgs(game)) == 6
    (target,) = events_of(game, type="wolf_target")
    assert target.payload["source"] == "engine_random"
    assert target.payload["target_id"] in {others[0].id, others[1].id}


def test_wolf_chat_cap_without_named_targets_picks_any_non_wolf():
    game = new_game()
    a, b = by_role(game, "wolf")
    run_day(game, Controlled(game, wolf_targets={a.seat: None, b.seat: None}))
    (target,) = events_of(game, type="wolf_target")
    assert target.payload["source"] == "engine_random"
    victim = Player.objects.get(pk=target.payload["target_id"])
    assert victim.role != "wolf"
    assert all(m.payload["kill_target_id"] is None for m in wolf_msgs(game))


def test_engine_random_kill_is_seeded():
    seats = []
    for _ in range(2):
        game = new_game(seed=21)
        a, b = by_role(game, "wolf")
        run_day(game, Controlled(game, wolf_targets={a.seat: None, b.seat: None}))
        target_id = events_of(game, type="wolf_target")[0].payload["target_id"]
        seats.append(Player.objects.get(pk=target_id).seat)
    assert seats[0] == seats[1]


def test_wolf_name_guard_falls_back_to_pass():
    game = new_game()
    a, b = by_role(game, "wolf")

    class Namer(Controlled):
        def wolf_step(self, player, day, n):
            mate = b if player.pk == a.pk else a
            return [("speak", {"message": f"hi {mate.name}", "kill_target": None})]

    run_day(game, Namer(game))
    assert wolf_msgs(game) == []
    passes = events_of(game, type="pass", phase="night_wolf_chat")
    assert len(passes) == 6
    assert passes[0].payload == {"phase": "night_wolf_chat"}
    assert passes[0].visibility == "engine"
    assert events_of(game, type="wolf_target")[0].payload["source"] == "engine_random"
    assert AgentCall.objects.filter(player=a).count() >= 3 * 3


def test_single_living_wolf_uses_its_latest_target():
    game = new_game()
    _, b = by_role(game, "wolf")
    kill(b)
    victim = non_wolves(game)[2]
    run_day(game, Controlled(game, kill=victim))
    assert len(wolf_msgs(game)) == 1
    assert events_of(game, type="wolf_target")[0].payload["source"] == "agreed"


# ----------------------------------------------------------- seer / notes


def test_seer_gets_one_notes_turn_and_cannot_speak():
    game = new_game()
    seer = by_role(game, "seer")[0]

    class Chatty(Controlled):
        def notes_step(self, player, day, n, kind):
            if player.role == "seer" and kind == "seer_notes":
                return [("speak", {"message": "I am the seer!"})]
            return super().notes_step(player, day, n, kind)

    run_day(game, Chatty(game, kill=non_wolves(game)[0]))
    done = [e for e in events_of(game, type="notes_turn_done", phase="night_seer")]
    assert [e.actor_id for e in done] == [seer.id]
    assert not any(
        "I am the seer" in e.payload.get("message", "") for e in events_of(game)
    )


def test_seer_gets_exactly_one_turn_when_working():
    game = new_game()
    seer = by_role(game, "seer")[0]
    run_day(game, Controlled(game, kill=by_role(game, "villager")[0]))
    # seer calls: night notes + (discussion/vote/day notes if alive)
    done = events_of(game, type="notes_turn_done", phase="night_seer")
    assert len(done) == 1 and done[0].actor_id == seer.id


def test_dead_seer_is_skipped():
    game = new_game()
    seer = by_role(game, "seer")[0]
    kill(seer)
    run_day(game, Controlled(game, kill=by_role(game, "villager")[0]))
    assert events_of(game, type="notes_turn_done", phase="night_seer") == []
    assert AgentCall.objects.filter(player=seer).count() == 0


def test_day_notes_one_turn_per_survivor_none_for_dead():
    game = new_game()
    dead_early = by_role(game, "villager")[0]
    kill(dead_early)
    victim = by_role(game, "villager")[1]
    run_day(game, Controlled(game, kill=victim))
    game = fresh(game)
    assert game.status == "active"
    done = events_of(game, type="notes_turn_done", phase="day_notes")
    survivors = {p.id for p in game.players.filter(alive=True)}
    assert sorted(e.actor_id for e in done) == sorted(survivors)
    assert dead_early.id not in {e.actor_id for e in done}
    assert victim.id not in {e.actor_id for e in done}


def test_dead_players_never_get_turns():
    game = new_game()
    dead = by_role(game, "villager")[0]
    kill(dead)
    run_day(game, Controlled(game, kill=by_role(game, "villager")[1]))
    assert AgentCall.objects.filter(player=dead).count() == 0


# ------------------------------------------------------------- discussion


def test_discussion_events_and_moderator_picks():
    game = new_game()
    run_day(game, ScriptedProvider(game))
    speeches = events_of(game, type="speech")
    picks = events_of(game, type="moderator_pick")
    assert speeches and all(s.visibility == "public" for s in speeches)
    assert all(p.phase == "discussion" for p in picks)
    assert picks[-1].payload["end"] is True
    assert len(speeches) >= game.config["discussion_min_messages"]


def test_discussion_pass_recorded_as_engine_event():
    game = new_game()

    class Passer(Controlled):
        def discussion_step(self, player, day, n):
            return [("pass", {})]

    run_day(game, Passer(game, kill=by_role(game, "villager")[0]))
    passes = events_of(game, type="pass", phase="discussion")
    assert len(passes) == 3  # three passes in a row end the discussion
    assert passes[0].payload == {"phase": "discussion"}
    assert events_of(game, type="speech") == []


# ----------------------------------------------------------------- budget


def test_budget_exceeded_aborts_and_returns_cleanly():
    game = new_game(config={"call_budget": 3})
    run_day(game, ScriptedProvider(game))
    game = fresh(game)
    assert game.status == "aborted"
    assert AgentCall.objects.filter(game=game).count() == 3
    run_day(game, ScriptedProvider(game))  # no-op afterwards


def test_llm_errors_fall_back_not_crash():
    game = new_game()

    class Boom:
        def respond(self, messages, tools):
            raise LLMError("down")

    class BoomProvider:
        def player_agent(self, player):
            return Boom()

        def moderator_agent(self):
            return Boom()

    run_day(game, BoomProvider())
    game = fresh(game)
    assert game.status == "active" and game.day_number == 2
    assert events_of(game, type="wolf_target")[0].payload["source"] == "engine_random"
