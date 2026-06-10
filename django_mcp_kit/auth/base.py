"""Pluggable authentication for the resource server.

An :class:`Authenticator` validates the incoming request and returns a Django
``User`` (or ``None``). Backends listed in ``DJANGO_MCP_KIT["AUTH_BACKENDS"]`` are
tried in order, so a deployment can support OAuth *and* static bearer at once.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .. import conf
from ..utils import import_object


class Authenticator:
    def authenticate(self, request):  # pragma: no cover - interface
        """Return a Django ``User`` or ``None``."""
        raise NotImplementedError

    def challenge(self):
        """Optional ``(status, headers)`` to send when no backend authenticates."""
        return None


def bearer_token(request):
    """Extract a ``Bearer`` token from a Django request or a header-mapping shim."""
    header = ""
    headers = getattr(request, "headers", None)
    if headers is not None:
        header = headers.get("Authorization") or headers.get("authorization") or ""
    else:
        header = getattr(request, "META", {}).get("HTTP_AUTHORIZATION", "")
    prefix = "Bearer "
    if header.startswith(prefix):
        return header[len(prefix):].strip()
    return None


def get_backends():
    return [import_object(path)() for path in conf.get_setting("AUTH_BACKENDS")]


def authenticate_request(request, backends=None):
    """Try each backend in order.

    Returns ``(user, None)`` on success, or ``(None, (status, headers))`` with the
    first backend's challenge when nothing authenticates.
    """
    backends = backends if backends is not None else get_backends()
    for backend in backends:
        user = backend.authenticate(request)
        if user is not None:
            return user, None
    for backend in backends:
        challenge = backend.challenge()
        if challenge:
            return None, challenge
    return None, (401, {"WWW-Authenticate": "Bearer"})


def resource_metadata_path():
    """RFC 9728 well-known path."""
    return "/.well-known/oauth-protected-resource"


def resource_metadata_url():
    """Absolute URL of the protected-resource metadata document."""
    resource = conf.get_setting("RESOURCE_SERVER_URL") or ""
    parsed = urlparse(resource)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{resource_metadata_path()}"
    return resource_metadata_path()
