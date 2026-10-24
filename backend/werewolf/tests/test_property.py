import re

import pytest

from werewolf.engine import ScriptedProvider, run_day
from werewolf.models import Game, GameEvent, PlayerNotes
from werewolf.tests.factories import create_classic_game, make_characters
from werewolf.tests.helpers import CapturingProvider, events_of, normalised_log

pytestmark = pytest.mark.django_db

TOKEN = re.compile(r"\[[^\[\]]+ d\d+ #\d+\]")
NOTE_TOKEN = re.compile(r"\[[^\[\]]+ d\d+ #\d+ note\]")


def play_to_end(game, provider, max_runs=12):
    for _ in range(max_runs):
        game.refresh_from_db()
        if game.status != Game.Status.ACTIVE:
            return
        run_day(game, provider)
    raise AssertionError("game did not finish")


def event_token(event):
    message = event.payload.get("message")
    if not message:
        return None
    found = TOKEN.search(message)
    return found.group(0) if found else None


def allowed(event, player):
    return (
        event.visibility == "public"
        or (event.visibility == "wolf_chat" and player.role in ("wolf", "seer"))
        or event.visibility == f"player:{player.id}"
    )


@pytest.mark.parametrize("seed", range(10))
def test_visibility_property(seed):
    make_characters(7)
    game = create_classic_game(seed=seed)
    capture = CapturingProvider(ScriptedProvider(game))
    play_to_end(game, capture)

    players = {p.id: p for p in game.players.all()}
    events = list(GameEvent.objects.filter(game=game).order_by("seq"))
    death_seq = {e.payload["player_id"]: e.seq for e in events if e.type == "death"}
    tokened = [(e, event_token(e)) for e in events if event_token(e)]
    assert tokened, "scripted games must produce tokenised events"
    assert capture.player_prompts

    for prompt in capture.player_prompts:
        player = players[prompt["player_id"]]
        assert player.id not in death_seq or death_seq[player.id] > prompt["max_seq"]
        for event, token in tokened:
            expected = (
                allowed(event, player)
                and event.day == prompt["day"]
                and event.seq <= prompt["max_seq"]
                and (player.id not in death_seq or event.seq <= death_seq[player.id])
            )
            assert (token in prompt["text"]) == expected, (
                f"seed {seed}: {token} for {player.name} ({player.role}) "
                f"{event.type}/{event.visibility}"
            )

    # Engine-only events never leak: their types never render and no engine
    # event carries a token.
    for event in events:
        if event.visibility == "engine":
            assert event_token(event) is None


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_end_to_end_note_canaries_never_leak(seed):
    make_characters(7)
    game = create_classic_game(seed=seed)
    capture = CapturingProvider(ScriptedProvider(game))
    play_to_end(game, capture)

    notes = list(PlayerNotes.objects.filter(game=game))
    assert notes
    for note in notes:
        canaries = NOTE_TOKEN.findall(note.text)
        assert canaries
        for prompt in capture.player_prompts:
            if prompt["player_id"] == note.player_id:
                continue
            for canary in canaries:
                assert canary not in prompt["text"]
        for text in capture.moderator_prompts:
            for canary in canaries:
                assert canary not in text


def test_moderator_prompts_never_contain_wolf_chat():
    make_characters(7)
    game = create_classic_game(seed=6)
    capture = CapturingProvider(ScriptedProvider(game))
    play_to_end(game, capture)
    wolf_tokens = [
        event_token(e) for e in events_of(game, type="wolf_message") if event_token(e)
    ]
    assert wolf_tokens and capture.moderator_prompts
    for text in capture.moderator_prompts:
        assert not any(t in text for t in wolf_tokens)
        assert "wolf" not in text.lower()


def test_log_window_day_two_prompts_have_no_day_one_events():
    make_characters(7)
    game = create_classic_game(seed=3)
    capture = CapturingProvider(ScriptedProvider(game))
    run_day(game, capture)
    game.refresh_from_db()
    assert game.status == "active" and game.day_number == 2
    day1_tokens = [event_token(e) for e in events_of(game, day=1) if event_token(e)]
    day1_prompts = len(capture.player_prompts)
    run_day(game, capture)
    day2_prompts = capture.player_prompts[day1_prompts:]
    assert day2_prompts
    for prompt in day2_prompts:
        assert prompt["day"] == 2
        assert not any(t in prompt["text"] for t in day1_tokens)
    # Day 1 survives only through notes.
    own_notes = {n.player_id: n.text for n in PlayerNotes.objects.filter(game=game)}
    carried = [
        p
        for p in day2_prompts
        if p["player_id"] in own_notes
        and any(
            t in p["text"]
            for t in NOTE_TOKEN.findall(own_notes[p["player_id"]])
            if " d1 " in t
        )
    ]
    assert carried


def test_replay_reproduces_event_log():
    from werewolf.agents import ReplayAgent
    from werewolf.turns import recorded_responses

    make_characters(7)
    game1 = create_classic_game(seed=12)
    play_to_end(game1, ScriptedProvider(game1))
    game2 = create_classic_game(seed=12)

    agent = ReplayAgent(recorded_responses(game1))

    class ReplayProvider:
        def player_agent(self, player):
            return agent

        def moderator_agent(self):
            return agent

    play_to_end(game2, ReplayProvider())
    assert normalised_log(game2) == normalised_log(game1)
    assert game2.status == game1.status and game2.winner == game1.winner
