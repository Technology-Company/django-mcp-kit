"""Single access point for the ``DJANGO_MCP_KIT`` settings dict.

Keeping every setting read in one place means the rest of the library never reaches
into ``django.conf.settings`` directly for its own config.
"""

from __future__ import annotations

from django.conf import settings

DEFAULTS = {
    "SERVER_NAME": "django-mcp-kit",
    "SERVER_VERSION": "0.1.0",
    "AUTH_BACKENDS": ["django_mcp_kit.auth.StaticBearer"],
    "TRANSPORT": "django_mcp_kit.transports.sdk",
    # OAuth resource-server params (see auth/oauth.py):
    "OAUTH_ISSUER_URL": None,
    "RESOURCE_SERVER_URL": None,
    "REQUIRED_SCOPES": ["mcp"],
    # Name shown on the OAuth consent page (the DOT Application.name).
    "OAUTH_APP_NAME": "MCP connector",
    # Transport security: opt-in, off by default.
    "DNS_REBINDING_PROTECTION": False,
    "STATELESS": True,
    "REQUIRE_AUTH": True,
    # Deployment:
    "TOPOLOGY": "separate",
    "PORT": 8810,
    # StaticBearer token -> user resolver (dotted path to a callable taking a token
    # string and returning a User or None). e.g. "myapp.models.UserProfile.user_for_token".
    "STATIC_BEARER_RESOLVER": None,
    # Per-user write rate limit used by RateLimitedMixin (count, window-seconds).
    "WRITE_RATE_LIMIT": (30, 60),
}


def get_setting(name, default=None):
    """Return ``DJANGO_MCP_KIT[name]``, falling back to the built-in default."""
    cfg = getattr(settings, "DJANGO_MCP_KIT", {}) or {}
    if name in cfg:
        return cfg[name]
    if name in DEFAULTS:
        return DEFAULTS[name]
    return default
