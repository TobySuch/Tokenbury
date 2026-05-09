from django.contrib import admin

from world.models import Agent, Location


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("slug", "name")
    prepopulated_fields = {"slug": ("name",)}
