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


def test_invalid_role_mix_shows_form_error(admin_client):
    make_characters(12)
    resp = _post(admin_client, config={"wolf_count": 0})
    assert resp.status_code == 200
    assert "at least 1 wolf" in str(resp.context["adminform"].form.errors["config"])
    assert not Game.objects.exists()


def test_settings_prefill_includes_new_keys(admin_client):
    initial = admin_client.get(ADD_URL).context["adminform"].form["config"].value()
    for key in ("player_count", "wolf_count", "lovers", "lovers_chat_max_messages"):
        assert f'"{key}"' in initial


def test_player_count_setting_drives_character_check(admin_client):
    make_characters(8)
    resp = _post(admin_client, config={"player_count": 10})
    assert resp.status_code == 200
    assert "needs 10 characters" in str(
        resp.context["adminform"].form.non_field_errors()
    )
    resp = _post(admin_client, config={"player_count": 8})
    assert resp.status_code == 302
    assert Game.objects.get().players.count() == 8


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


def test_admin_created_games_start_unpublished(admin_client):
    make_characters()
    _post(admin_client)
    assert Game.objects.get().published is False


def test_publish_toggle_on_change_page_and_list(admin_client):
    make_characters()
    _post(admin_client, seed="1")
    game = Game.objects.get()
    form = (
        admin_client
        .get(f"/admin/werewolf/game/{game.pk}/change/")
        .context["adminform"]
        .form
    )
    assert "published" in form.fields
    changelist = admin_client.get("/admin/werewolf/game/").context["cl"]
    assert "published" in changelist.list_display
    assert "published" in changelist.list_filter


def test_publish_and_unpublish_actions(admin_client):
    make_characters()
    _post(admin_client, seed="1")
    game = Game.objects.get()
    admin_client.post(
        "/admin/werewolf/game/",
        {"action": "publish_games", "_selected_action": [game.pk]},
    )
    game.refresh_from_db()
    assert game.published is True
    admin_client.post(
        "/admin/werewolf/game/",
        {"action": "unpublish_games", "_selected_action": [game.pk]},
    )
    game.refresh_from_db()
    assert game.published is False


def _two_games(admin_client):
    make_characters(8)
    _post(admin_client, seed="1")
    _post(admin_client, seed="2")
    return Game.objects.order_by("pk")


def test_inline_lover_choices_are_limited_to_the_game(admin_client):
    game, other = _two_games(admin_client)
    resp = admin_client.get(f"/admin/werewolf/game/{game.pk}/change/")
    formset = resp.context["inline_admin_formsets"][0].formset
    for form in formset.forms:
        choices = set(form.fields["lover"].queryset)
        assert choices == set(game.players.exclude(pk=form.instance.pk))
        assert not choices & set(other.players.all())


def test_player_admin_lover_choices_are_limited_to_the_game(admin_client):
    game, _ = _two_games(admin_client)
    player = game.players.first()
    resp = admin_client.get(f"/admin/werewolf/player/{player.pk}/change/")
    queryset = resp.context["adminform"].form.fields["lover"].queryset
    assert set(queryset) == set(game.players.exclude(pk=player.pk))


def test_lover_from_another_game_is_rejected(admin_client):
    game, other = _two_games(admin_client)
    player = game.players.first()
    stranger = other.players.first()
    resp = admin_client.post(
        f"/admin/werewolf/player/{player.pk}/change/",
        {
            "game": game.pk,
            "character": player.character_id,
            "seat": player.seat,
            "role": player.role,
            "alive": "on",
            "lover": stranger.pk,
        },
    )
    assert resp.status_code == 200
    assert "lover" in resp.context["adminform"].form.errors
    player.refresh_from_db()
    assert player.lover_id != stranger.pk


def test_lover_check_uses_the_submitted_game(admin_client):
    game, other = _two_games(admin_client)
    player = game.players.first()
    resp = admin_client.post(
        f"/admin/werewolf/player/{player.pk}/change/",
        {
            "game": other.pk,
            "character": player.character_id,
            "seat": 99,
            "role": player.role,
            "lover": game.players.last().pk,
        },
    )
    assert resp.status_code == 200
    errors = resp.context["adminform"].form.errors["lover"]
    assert "A lover must be in the same game." in errors
