"""Topology B (singleserver) wiring. Skipped if singleserver absent."""

import pytest

pytest.importorskip("singleserver")

from django_mcp_kit import services


def test_mcp_server_health_check_is_healthz():
    services.mcp_server.cache_clear()
    server = services.mcp_server()
    # Health check must NOT be /mcp (that 4xx's -> restart loop).
    assert server.health_check_url == "/healthz"
    assert server.port == 8810  # conf default


def test_mcp_server_command_includes_runserver_mcp():
    services.mcp_server.cache_clear()
    server = services.mcp_server()
    # `.command` resolves the {port} placeholder; runserver_mcp must be present.
    assert any("runserver_mcp" in part for part in server.command)
    assert "8810" in server.command
