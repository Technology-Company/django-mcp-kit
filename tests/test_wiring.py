"""ASGI wiring + transport-security + the unimplemented HTTP transport."""

import asyncio

import pytest

pytest.importorskip("mcp")

from django_mcp_kit import asgi
from django_mcp_kit.transports import http, sdk


def test_http_transport_not_implemented():
    with pytest.raises(NotImplementedError):
        http.build_application()


def test_transport_security_off_by_default():
    ts = sdk._transport_security()
    assert ts.enable_dns_rebinding_protection is False


def test_transport_security_on_populates_hosts(settings):
    settings.DJANGO_MCP_KIT = {**settings.DJANGO_MCP_KIT, "DNS_REBINDING_PROTECTION": True}
    ts = sdk._transport_security()
    assert ts.enable_dns_rebinding_protection is True
    assert "testserver" in ts.allowed_hosts
    assert "*" not in ts.allowed_hosts  # wildcard never lands in the allowlist


def test_get_application_returns_callable():
    assert callable(asgi.get_application())


def test_mount_delegates_non_mcp_paths_to_django():
    seen = {}

    async def fake_django(scope, receive, send):
        seen["path"] = scope["path"]

    app = asgi.mount(fake_django)

    async def receive():
        return {"type": "http.request"}

    async def send(_):
        pass

    asyncio.run(app({"type": "http", "path": "/some/site/page"}, receive, send))
    assert seen["path"] == "/some/site/page"
