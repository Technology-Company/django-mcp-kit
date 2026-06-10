"""Discovery + health endpoints for the Django site.

The MCP wire endpoint (``/mcp``) is ASGI-only and served by the transport's ASGI app
(standalone process, or mounted via :func:`django_mcp_kit.asgi.mount`). These Django
views provide the RFC 9728 protected-resource metadata and a liveness probe that the
``singleserver`` health check points at (NOT ``/mcp``).
"""

from __future__ import annotations

from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_http_methods

from .auth.oauth import protected_resource_metadata


@require_http_methods(["GET"])
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
def oauth_protected_resource(request):
    return JsonResponse(protected_resource_metadata())


app_name = "django_mcp_kit"

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path(".well-known/oauth-protected-resource", oauth_protected_resource, name="oauth-protected-resource"),
]
