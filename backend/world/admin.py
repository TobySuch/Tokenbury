from django.contrib import admin

from world.models import Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("slug", "name")
    prepopulated_fields = {"slug": ("name",)}
