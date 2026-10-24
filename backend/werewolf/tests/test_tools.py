import pytest

from werewolf.tools import (
    NOTE_TOOLS,
    TERMINAL_TOOLS,
    ValidationContext,
    tools_for,
    validate_tool_call,
)


def ctx(**kw):
    base = {
        "turn_kind": "discussion",
        "actor_role": "villager",
        "actor_alive": True,
        "wolf_names": ["Wanda", "Wilf"],
        "living_names": ["Alice", "Bob", "Wanda", "Wilf", "Vera"],
        "living_non_wolf_names": ["Alice", "Bob", "Vera"],
        "speech_max_chars": 400,
        "actor_name": "Alice",
    }
    base.update(kw)
    return ValidationContext(**base)


def names(kind):
    return {t["function"]["name"] for t in tools_for(kind)}


def test_constants():
    assert TERMINAL_TOOLS == {"speak", "pass", "vote"}
    assert NOTE_TOOLS == {"append_note", "replace_notes"}


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("wolf_chat", {"speak", "pass", "append_note", "replace_notes"}),
        ("seer_notes", {"pass", "append_note", "replace_notes"}),
        ("discussion", {"speak", "pass", "append_note", "replace_notes"}),
        ("vote", {"vote", "append_note", "replace_notes"}),
        ("day_notes", {"pass", "append_note", "replace_notes"}),
    ],
)
def test_tools_for(kind, expected):
    assert names(kind) == expected


def speak_props(kind):
    (t,) = [t for t in tools_for(kind) if t["function"]["name"] == "speak"]
    return t["function"]["parameters"]["properties"]


def test_kill_target_only_in_wolf_chat_schema():
    assert "kill_target" in speak_props("wolf_chat")
    assert "kill_target" not in speak_props("discussion")


def test_replace_notes_warns():
    (t,) = [t for t in tools_for("vote") if t["function"]["name"] == "replace_notes"]
    assert "drop" in t["function"]["description"]


def test_valid_calls():
    assert validate_tool_call("speak", {"message": "hello"}, ctx()) is None
    assert validate_tool_call("pass", {}, ctx()) is None
    assert validate_tool_call("append_note", {"text": "x"}, ctx()) is None
    assert validate_tool_call("replace_notes", {"text": "x"}, ctx()) is None
    assert validate_tool_call("vote", {"target": "bob"}, ctx(turn_kind="vote")) is None
    assert validate_tool_call("vote", {"target": "none"}, ctx(turn_kind="vote")) is None
    w = ctx(turn_kind="wolf_chat", actor_role="wolf", actor_name="Wanda")
    assert (
        validate_tool_call(
            "speak", {"message": "Fancy Alice?", "kill_target": "ALICE"}, w
        )
        is None
    )
    assert validate_tool_call("speak", {"message": "hmm"}, w) is None


def test_unknown_tool():
    assert validate_tool_call("fly", {}, ctx())


def test_wrong_phase():
    assert validate_tool_call("vote", {"target": "Bob"}, ctx())
    assert validate_tool_call("speak", {"message": "hi"}, ctx(turn_kind="vote"))
    assert validate_tool_call("speak", {"message": "hi"}, ctx(turn_kind="day_notes"))


def test_seer_cannot_speak_at_night():
    err = validate_tool_call(
        "speak", {"message": "hi"}, ctx(turn_kind="seer_notes", actor_role="seer")
    )
    assert err
    assert "seer" in err.lower()


def test_dead_actor():
    assert validate_tool_call("pass", {}, ctx(actor_alive=False))


@pytest.mark.parametrize(
    "args", [{}, {"message": ""}, {"message": "  "}, {"message": 3}]
)
def test_bad_message(args):
    assert validate_tool_call("speak", args, ctx())


def test_message_too_long():
    assert validate_tool_call("speak", {"message": "x" * 401}, ctx())
    assert validate_tool_call("speak", {"message": "x" * 400}, ctx()) is None


def test_wolf_name_guard():
    w = ctx(turn_kind="wolf_chat", actor_role="wolf", actor_name="Wanda")
    for msg in ("I am wanda", "WILF is quiet", "what about Wilf, though?"):
        err = validate_tool_call("speak", {"message": msg}, w)
        assert err
        assert "Wolf A" in err
    assert validate_tool_call("speak", {"message": "Wilfred is nice"}, w) is None


@pytest.mark.parametrize("target", ["Wanda", "Nobody", "", 5])
def test_bad_kill_target(target):
    w = ctx(turn_kind="wolf_chat", actor_role="wolf", actor_name="Wanda")
    assert validate_tool_call("speak", {"message": "ok", "kill_target": target}, w)


@pytest.mark.parametrize("target", ["Alice", "Nobody", "", None, 5])
def test_bad_vote_target(target):
    assert validate_tool_call("vote", {"target": target}, ctx(turn_kind="vote"))


def test_vote_missing_target():
    assert validate_tool_call("vote", {}, ctx(turn_kind="vote"))


def test_empty_note():
    assert validate_tool_call("append_note", {"text": " "}, ctx())
    assert validate_tool_call("replace_notes", {}, ctx())
    assert validate_tool_call("append_note", {"text": 1}, ctx())


def test_speak_schema_states_the_character_cap():
    from werewolf.tools import tools_for

    (speak,) = [
        t for t in tools_for("discussion", 250) if t["function"]["name"] == "speak"
    ]
    desc = speak["function"]["parameters"]["properties"]["message"]["description"]
    assert "250 characters" in desc
