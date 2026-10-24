import json

from django import forms
from django.contrib import admin
from django.contrib.admin.options import IS_POPUP_VAR
from django.utils.html import format_html

from werewolf.config import DEFAULT_CONFIG, build_config
from werewolf.models import (
    AgentCall,
    Character,
    Game,
    GameEvent,
    Player,
    PlayerNotes,
)
from werewolf.setup import create_game


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "talkativeness")


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    raw_id_fields = ("character",)


class PrettyJSONField(forms.JSONField):
    def prepare_value(self, value):
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2)


class GameCreationForm(forms.ModelForm):
    """Add form: a game is created through create_game, not by saving a bare row."""

    seed = forms.IntegerField(
        required=False, help_text="Leave blank for a random seed."
    )
    config = PrettyJSONField(
        initial=DEFAULT_CONFIG,
        widget=forms.Textarea(attrs={"rows": 16, "cols": 50}),
        help_text="Game settings. Any key left out uses its default.",
    )

    class Meta:
        model = Game
        fields = ["seed", "config"]

    def clean_config(self):
        config = self.cleaned_data["config"]
        if not isinstance(config, dict):
            raise forms.ValidationError("Settings must be a JSON object.")
        try:
            return build_config(config)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean(self):
        cleaned = super().clean()
        config = cleaned.get("config")
        if config is None:
            return cleaned  # config already failed validation
        needed = config["player_count"]
        count = Character.objects.count()
        if count < needed:
            raise forms.ValidationError(
                f"A game needs {needed} characters but only {count} exist. "
                "Add more, or run `manage.py seed_werewolf_characters`."
            )
        return cleaned


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "seed",
        "status",
        "phase",
        "day_number",
        "winner",
        "published",
        "created_at",
    )
    list_filter = ("published", "status", "phase", "winner")
    actions = ["publish_games", "unpublish_games"]
    inlines = [PlayerInline]
    readonly_fields = (
        "seed",
        "phase",
        "day_number",
        "winner",
        "created_at",
        "settings",
    )
    fields = ("published", "status", *readonly_fields)

    @admin.action(description="Publish selected games")
    def publish_games(self, request, queryset):
        queryset.update(published=True)

    @admin.action(description="Unpublish selected games")
    def unpublish_games(self, request, queryset):
        queryset.update(published=False)

    @admin.display(description="Settings")
    def settings(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.config, indent=2))

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = GameCreationForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        return ("seed", "config") if obj is None else self.fields

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields

    def get_inlines(self, request, obj):
        return self.inlines if obj else []

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        game = create_game(
            seed=form.cleaned_data["seed"], config=form.cleaned_data["config"]
        )
        # Point the admin's object at the fully set-up game for the redirect.
        obj.pk = game.pk
        obj.refresh_from_db()

    def response_add(self, request, obj, post_url_continue=None):
        # Land on the new game (with its cast and roles) rather than the list.
        if "_addanother" not in request.POST and IS_POPUP_VAR not in request.POST:
            request.POST = request.POST.copy()
            request.POST["_continue"] = "1"
        return super().response_add(request, obj, post_url_continue)


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
