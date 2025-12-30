from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static

# Swagger imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny


def home(request):
    return HttpResponse("Django backend is running! Try /api/desktop/ or /api/mobile/")


#  Swagger schema with JWT support
schema_view = get_schema_view(
    openapi.Info(
        title="IWMS Backend API",
        default_version="v1",
        description="IWMS API with JWT Authentication",
    ),
    public=True,
    permission_classes=(AllowAny,),
)


urlpatterns = [
    # Home
    path("", home),

    # APIs
    path("api/desktop/", include("api.urls.desktop_urls")),
    path("api/mobile/", include("api.urls.mobile_urls")),

    # Swagger UI
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
