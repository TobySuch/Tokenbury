from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

PUBLIC = "public"
WOLF_CHAT = "wolf_chat"
ENGINE = "engine"


def player_visibility(player_id: int) -> str:
    return f"player:{player_id}"


class Character(models.Model):
    name = models.CharField(max_length=100, unique=True)
    talkativeness = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    avatar = models.ImageField(upload_to="werewolf/avatars")

    def __str__(self):
        return self.name


class Game(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        FINISHED = "finished"
        ABORTED = "aborted"

    class Phase(models.TextChoices):
        SETUP = "setup"
        NIGHT_WOLF_CHAT = "night_wolf_chat"
        NIGHT_SEER = "night_seer"
        MORNING = "morning"
        DISCUSSION = "discussion"
        VOTE = "vote"
        ELIMINATION = "elimination"
        DAY_NOTES = "day_notes"
        GAME_OVER = "game_over"

    class Winner(models.TextChoices):
        WOLVES = "wolves"
        TOWN = "town"
        DRAW = "draw"

    seed = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    phase = models.CharField(max_length=30, choices=Phase.choices, default=Phase.SETUP)
    day_number = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    winner = models.CharField(
        max_length=20, choices=Winner.choices, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Game {self.pk} (seed {self.seed})"


class Player(models.Model):
    class Role(models.TextChoices):
        WOLF = "wolf"
        SEER = "seer"
        VILLAGER = "villager"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="players")
    character = models.ForeignKey(
        Character, on_delete=models.PROTECT, related_name="players"
    )
    seat = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=20, choices=Role.choices)
    alive = models.BooleanField(default=True)
    wolf_label = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        ordering = ["seat"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "seat"], name="werewolf_unique_game_seat"
            ),
            models.UniqueConstraint(
                fields=["game", "character"], name="werewolf_unique_game_character"
            ),
        ]

    @property
    def name(self):
        return self.character.name

    def __str__(self):
        return f"{self.character.name} ({self.role})"


class GameEvent(models.Model):
    class Type(models.TextChoices):
        ROLE_ASSIGNED = "role_assigned"
        WOLF_MESSAGE = "wolf_message"
        WOLF_TARGET = "wolf_target"
        DEATH = "death"
        SPEECH = "speech"
        VOTE_CAST = "vote_cast"
        VOTE_RESULT = "vote_result"
        MODERATOR_PICK = "moderator_pick"
        PHASE_CHANGE = "phase_change"
        GAME_OVER = "game_over"
        # Spec extensions: let loop progress be derived from the log.
        PASS = "pass"
        NOTES_TURN_DONE = "notes_turn_done"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="events")
    seq = models.PositiveIntegerField()
    day = models.PositiveIntegerField()
    phase = models.CharField(max_length=30, choices=Game.Phase.choices)
    type = models.CharField(max_length=30, choices=Type.choices)
    visibility = models.CharField(max_length=40)
    actor = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "seq"], name="werewolf_unique_game_seq"
            ),
        ]

    def __str__(self):
        return f"#{self.seq} {self.type} ({self.visibility})"


class PlayerNotes(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="notes")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="notes")
    version = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    at_seq = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["player_id", "version"]
        verbose_name_plural = "player notes"
        constraints = [
            models.UniqueConstraint(
                fields=["player", "version"], name="werewolf_unique_player_version"
            ),
        ]

    def __str__(self):
        return f"{self.player} notes v{self.version}"


class AgentCall(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="calls")
    player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    prompt = models.TextField()
    response = models.TextField(blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Call {self.pk} ({self.player or 'moderator'})"
