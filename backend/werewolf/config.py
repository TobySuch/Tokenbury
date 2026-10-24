DEFAULT_CONFIG = {
    "reveal_role_on_death": True,
    "votes_public": True,
    "wolf_chat_max_messages": 6,
    "discussion_max_messages": 30,
    "discussion_max_per_player": 6,
    "discussion_min_messages": 6,
    "max_days": 8,
    "notes_max_chars": 3000,
    "speech_max_chars": 400,
    "max_note_calls_per_turn": 4,
    "call_budget": 400,
    "call_timeout_seconds": 60,
}

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


def _coerce(key, value, default):
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
            return value.strip().lower() in _TRUE
        raise ValueError(f"Config {key!r} must be a boolean, got {value!r}")
    try:
        return int(value)
    except TypeError, ValueError:
        raise ValueError(f"Config {key!r} must be an integer, got {value!r}") from None


def build_config(overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    unknown = sorted(set(overrides) - set(DEFAULT_CONFIG))
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(unknown)}")
    config = dict(DEFAULT_CONFIG)
    for key, value in overrides.items():
        config[key] = _coerce(key, value, DEFAULT_CONFIG[key])
    return config


def game_config(game) -> dict:
    return build_config(game.config)
