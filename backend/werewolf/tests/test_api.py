import pytest
from rest_framework.test import APIClient

from werewolf.models import Game, PlayerNotes
from werewolf.tests.factories import create_classic_game, make_characters

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def game():
    make_characters(7)
    return create_classic_game(seed=2, published=True)


def test_game_list_newest_first_and_shape(client, game):
    newer = Game.objects.create(seed=9, published=True)
    data = client.get("/api/werewolf/games/").json()
    assert [g["id"] for g in data] == [newer.id, game.id]
    assert set(data[0]) == {
        "id",
        "status",
        "phase",
        "day_number",
        "winner",
        "created_at",
    }


def test_game_detail_and_404(client, game):
    assert client.get(f"/api/werewolf/games/{game.id}/").json()["id"] == game.id
    assert client.get("/api/werewolf/games/9999/").status_code == 404


def test_players(client, game):
    p = game.players.order_by("seat").first()
    p.character.avatar = "werewolf/avatars/a.png"
    p.character.save()
    data = client.get(f"/api/werewolf/games/{game.id}/players/").json()
    assert [d["seat"] for d in data] == sorted(d["seat"] for d in data)
    assert len(data) == 7
    assert set(data[0]) == {
        "id",
        "name",
        "seat",
        "avatar_url",
        "role",
        "wolf_label",
        "alive",
    }
    assert data[0]["avatar_url"] == "http://testserver/media/werewolf/avatars/a.png"
    assert data[1]["avatar_url"] is None or data[1]["avatar_url"].startswith("http")
    assert data[0]["role"] == p.role
    assert client.get("/api/werewolf/games/9999/players/").status_code == 404


def test_beats_and_after(client, game):
    from werewolf.engine import ScriptedProvider, run_day

    run_day(game, ScriptedProvider(game))
    url = f"/api/werewolf/games/{game.id}/beats/"
    beats = client.get(url).json()
    assert beats[0]["index"] == 0 and len(beats) > 3
    rest = client.get(url + "?after=2").json()
    assert [b["index"] for b in rest] == [b["index"] for b in beats[3:]]
    assert client.get(url + "?after=abc").status_code == 400
    assert client.get("/api/werewolf/games/9999/beats/").status_code == 404


def test_notes(client, game):
    p = game.players.first()
    for v, seq in ((1, 5), (2, 9)):
        PlayerNotes.objects.create(
            game=game, player=p, version=v, text=f"v{v}", at_seq=seq
        )
    url = f"/api/werewolf/games/{game.id}/notes/"
    assert client.get(url, {"player": p.id, "at": 9}).json() == {
        "player_id": p.id, "version": 2, "text": "v2", "at_seq": 9,
    }  # fmt: skip
    assert client.get(url, {"player": p.id, "at": 6}).json()["version"] == 1
    assert client.get(url, {"player": p.id, "at": 1}).json() == {
        "player_id": p.id, "version": 0, "text": "", "at_seq": 0,
    }  # fmt: skip
    assert client.get(url).status_code == 400
    assert client.get(url, {"player": "x", "at": 1}).status_code == 400
    assert client.get(url, {"player": p.id}).status_code == 400
    assert client.get(url, {"player": 99999, "at": 1}).status_code == 404


def test_unpublished_games_are_hidden(client, game):
    hidden = create_classic_game(seed=3)
    assert hidden.published is False
    ids = [g["id"] for g in client.get("/api/werewolf/games/").json()]
    assert ids == [game.id]
    player = hidden.players.first()
    for path in ["", "players/", "beats/", f"notes/?player={player.id}&at=1"]:
        resp = client.get(f"/api/werewolf/games/{hidden.id}/{path}")
        assert resp.status_code == 404, path
