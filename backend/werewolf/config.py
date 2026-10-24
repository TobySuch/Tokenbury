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
    "player_count": 7,
    # None means "auto": derived from player_count by role_counts().
    "wolf_count": None,
    "seer_count": None,
    "doctor_count": None,
    "lovers": True,
    "lovers_chat_max_messages": 4,
}

MIN_PLAYERS = 5
MAX_PLAYERS = 12

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}
_AUTO = {"", "null", "none", "auto"}


def _coerce(key, value, default):
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
            return value.strip().lower() in _TRUE
        raise ValueError(f"Config {key!r} must be a boolean, got {value!r}")
    if default is None and (value is None or str(value).strip().lower() in _AUTO):
        return None
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
    role_counts(config)
    return config


def role_counts(config: dict) -> dict[str, int]:
    """Role mix for a game: auto from player_count, with optional overrides.

    Raises ValueError if the resulting mix is not playable.
    """
    players = config["player_count"]
    if not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise ValueError(
            f"player_count must be between {MIN_PLAYERS} and {MAX_PLAYERS}, "
            f"got {players}"
        )
    auto = {
        "wolf": max(1, round(players / 3.5)),
        "seer": 1,
        "doctor": 1 if players >= 6 else 0,
    }
    counts = {}
    for role, default in auto.items():
        override = config.get(f"{role}_count")
        counts[role] = default if override is None else override
        if counts[role] < 0:
            raise ValueError(f"{role}_count must not be negative")
    if counts["wolf"] < 1:
        raise ValueError("A game needs at least 1 wolf")
    if counts["seer"] > 1:
        raise ValueError("A game can have at most 1 seer")
    if counts["doctor"] > 1:
        raise ValueError("A game can have at most 1 doctor")
    if counts["wolf"] * 2 >= players:
        raise ValueError(
            f"Wolves must be fewer than everyone else: {counts['wolf']} wolves "
            f"in {players} players"
        )
    special = sum(counts.values())
    if special > players:
        raise ValueError(f"Role counts ({special}) exceed player_count ({players})")
    counts["villager"] = players - special
    return counts


def game_config(game) -> dict:
    return build_config(game.config)
