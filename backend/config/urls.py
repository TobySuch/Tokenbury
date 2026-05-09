from django.contrib import admin
from django.urls import path
from world.views import health, locations

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/locations/", locations),
]
