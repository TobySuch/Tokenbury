from django.contrib import admin

from werewolf.models import (
    AgentCall,
    Character,
    Game,
    GameEvent,
    Player,
    PlayerNotes,
)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "talkativeness")


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    raw_id_fields = ("character",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "seed",
        "status",
        "phase",
        "day_number",
        "winner",
        "created_at",
    )
    list_filter = ("status", "phase", "winner")
    inlines = [PlayerInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("game", "seat", "character", "role", "alive", "wolf_label")
    list_filter = ("game", "role", "alive")
    raw_id_fields = ("game", "character")


@admin.register(GameEvent)
class GameEventAdmin(admin.ModelAdmin):
    list_display = ("game", "seq", "day", "phase", "type", "visibility", "actor")
    list_filter = ("game", "type", "visibility", "day")
    raw_id_fields = ("game", "actor")
    ordering = ("game", "seq")


@admin.register(PlayerNotes)
class PlayerNotesAdmin(admin.ModelAdmin):
    list_display = ("player", "version", "at_seq", "created_at")
    list_filter = ("game",)
    raw_id_fields = ("game", "player")


@admin.register(AgentCall)
class AgentCallAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "player", "tokens_in", "tokens_out", "latency_ms")
    list_filter = ("game",)
    raw_id_fields = ("game", "player")
