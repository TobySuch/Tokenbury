from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from world.views import (
    agent_detail,
    health,
    locations,
    tick_days,
    tick_detail,
    tick_latest,
    tick_list,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/agents/<int:pk>/", agent_detail),
    path("api/locations/", locations),
    path("api/ticks/", tick_list),
    path("api/ticks/days/", tick_days),
    path("api/ticks/latest/", tick_latest),
    path("api/ticks/<int:pk>/", tick_detail),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
