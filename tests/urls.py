from django.urls import include, path

urlpatterns = [
    path("", include("django_mcp_kit.urls")),
]
