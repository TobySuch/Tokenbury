import html
import json

import pytest

from werewolf.config import DEFAULT_CONFIG
from werewolf.models import Game, GameEvent, Player
from werewolf.tests.factories import make_characters

pytestmark = pytest.mark.django_db

ADD_URL = "/admin/werewolf/game/add/"


def _post(admin_client, seed="", config=None):
    return admin_client.post(
        ADD_URL,
        {
            "seed": seed,
            "config": json.dumps(DEFAULT_CONFIG if config is None else config),
        },
    )


def test_add_form_prepopulates_default_settings(admin_client):
    resp = admin_client.get(ADD_URL)
    assert resp.status_code == 200
    initial = resp.context["adminform"].form["config"].value()
    assert json.loads(initial) == DEFAULT_CONFIG
    # Pretty-printed so it's editable by hand.
    assert '\n  "reveal_role_on_death": true' in initial


def test_add_form_only_asks_for_seed_and_settings(admin_client):
    form = admin_client.get(ADD_URL).context["adminform"].form
    assert set(form.fields) == {"seed", "config"}
    assert form.fields["seed"].required is False


def test_adding_a_game_runs_full_setup(admin_client):
    make_characters()
    config = {**DEFAULT_CONFIG, "max_days": 5, "votes_public": False}

    resp = _post(admin_client, seed="42", config=config)

    game = Game.objects.get()
    assert resp.status_code == 302
    assert resp.url == f"/admin/werewolf/game/{game.pk}/change/"
    assert game.seed == 42
    assert game.config["max_days"] == 5
    assert game.config["votes_public"] is False
    assert game.status == Game.Status.ACTIVE
    assert game.phase == Game.Phase.NIGHT_WOLF_CHAT
    assert game.day_number == 1
    assert Player.objects.filter(game=game).count() == 7
    assert GameEvent.objects.filter(game=game, type="role_assigned").count() == 7


def test_partial_settings_are_merged_with_defaults(admin_client):
    make_characters()
    _post(admin_client, config={"max_days": 3})
    game = Game.objects.get()
    assert game.config == {**DEFAULT_CONFIG, "max_days": 3}


def test_blank_seed_picks_one(admin_client):
    make_characters()
    _post(admin_client)
    assert Game.objects.get().seed is not None


@pytest.mark.parametrize(
    "config, message",
    [
        ({"nonsense": 1}, "Unknown config keys: nonsense"),
        ({"max_days": "lots"}, "must be an integer"),
    ],
)
def test_invalid_settings_show_an_error(admin_client, config, message):
    make_characters()
    resp = _post(admin_client, config=config)
    assert resp.status_code == 200
    assert message in str(resp.context["adminform"].form.errors["config"])
    assert not Game.objects.exists()


def test_settings_must_be_a_json_object(admin_client):
    make_characters()
    resp = admin_client.post(ADD_URL, {"seed": "", "config": "[1, 2]"})
    assert resp.status_code == 200
    assert "config" in resp.context["adminform"].form.errors
    assert not Game.objects.exists()


def test_too_few_characters_explains_how_to_seed_them(admin_client):
    make_characters(3)
    resp = _post(admin_client)
    assert resp.status_code == 200
    errors = str(resp.context["adminform"].form.non_field_errors())
    assert "seed_werewolf_characters" in errors
    assert not Game.objects.exists()


def test_change_page_shows_settings_read_only(admin_client):
    make_characters()
    _post(admin_client, seed="1")
    game = Game.objects.get()

    resp = admin_client.get(f"/admin/werewolf/game/{game.pk}/change/")

    assert resp.status_code == 200
    form = resp.context["adminform"].form
    assert "config" not in form.fields
    assert "seed" not in form.fields
    assert "status" in form.fields  # can still abort a game by hand
    assert '"max_days": 8' in html.unescape(resp.content.decode())
