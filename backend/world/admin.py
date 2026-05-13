from django.contrib import admin

from world.models import Agent, AgentTick, DailyPlan, Instance, Location, Tick


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "created_at")
    list_filter = ("active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("slug", "name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tick)
class TickAdmin(admin.ModelAdmin):
    list_display = ("id", "in_game_time", "created_at")
    ordering = ("-in_game_time",)


@admin.register(AgentTick)
class AgentTickAdmin(admin.ModelAdmin):
    list_display = ("agent", "tick", "location", "mood")
    list_filter = ("tick", "mood")
    raw_id_fields = ("agent", "tick", "location")


@admin.register(DailyPlan)
class DailyPlanAdmin(admin.ModelAdmin):
    list_display = ("agent", "date", "generated_at_tick")
    list_filter = ("date",)
    raw_id_fields = ("agent", "generated_at_tick")
