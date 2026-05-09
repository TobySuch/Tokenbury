from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from world.views import health, locations

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/locations/", locations),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
