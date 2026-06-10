"""Minimal Django settings for the self-contained test suite."""

SECRET_KEY = "test-only-not-secret"
DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "oauth2_provider",
    "wagtail.contrib.settings",
    "wagtail",
    "django_mcp_kit",
    "django_mcp_kit.wagtail_connector",
    "tests.dummyapp",
]

OAUTH2_PROVIDER = {"SCOPES": {"mcp": "Use MCP"}}
WAGTAIL_SITE_NAME = "test"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Build dummyapp tables directly from models (no migration files needed).
MIGRATION_MODULES = {"dummyapp": None}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "tests.urls"

DJANGO_MCP_KIT = {
    "SERVER_NAME": "test-mcp",
    "WRITE_RATE_LIMIT": (2, 60),
    "AUTH_BACKENDS": [
        "django_mcp_kit.auth.OAuthResourceServer",
        "django_mcp_kit.auth.StaticBearer",
    ],
    "OAUTH_ISSUER_URL": "https://example.test",
    "RESOURCE_SERVER_URL": "https://example.test/mcp",
    "REQUIRED_SCOPES": ["mcp"],
    "STATIC_BEARER_RESOLVER": "tests.dummyapp.tokens:user_for_token",
}
