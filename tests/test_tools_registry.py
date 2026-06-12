"""Tests for permissions, the enabled gate, rate limiting, autodiscovery, resources."""

import asyncio
import json

import pytest

from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.registry import tool_registry, resource_registry


def run(coro):
    return asyncio.run(coro)


def test_autodiscovered_tools_registered():
    # dummyapp/mcp_tools.py registers these on app load.
    names = {t.name for t in tool_registry.all(include_disabled=True)}
    assert {"echo", "secret", "snapshot", "add", "whoami"} <= names


def test_enabled_gate_hides_tool(settings):
    settings.MCP_ALLOW_PUBLISH = False
    visible = {t.name for t in tool_registry.all()}
    assert "publish" not in visible

    settings.MCP_ALLOW_PUBLISH = True
    visible = {t.name for t in tool_registry.all()}
    assert "publish" in visible


def test_permission_denied():
    d = MCPDispatcher(tools=tool_registry)
    blocks, is_error = run(d.call_tool("secret", {}, user=None))
    assert is_error is True
    assert "Nope." in blocks[0]["text"]


def test_tool_decorator_passes_user():
    d = MCPDispatcher(tools=tool_registry)

    class FakeUser:
        username = "alice"

    blocks, is_error = run(d.call_tool("whoami", {}, user=FakeUser()))
    assert json.loads(blocks[0]["text"]) == {"user": "alice"}


def test_decorator_input_schema():
    d = MCPDispatcher(tools=tool_registry)
    add = next(t for t in d.list_tools() if t["name"] == "add")
    props = add["inputSchema"]["properties"]
    assert props["a"]["type"] == "integer"
    # b has a default -> not required
    assert "a" in add["inputSchema"]["required"]
    assert "b" not in add["inputSchema"].get("required", [])


@pytest.mark.django_db
def test_rate_limited_mixin(settings):
    # WRITE_RATE_LIMIT is (2, 60) in test settings; 3rd call is throttled.
    from django.core.cache import cache

    cache.clear()
    d = MCPDispatcher(tools=tool_registry)

    class U:
        pk = 1

    user = U()
    assert run(d.call_tool("snapshot", {}, user=user))[1] is False
    assert run(d.call_tool("snapshot", {}, user=user))[1] is False
    blocks, is_error = run(d.call_tool("snapshot", {}, user=user))
    assert is_error is True
    assert "rate limit" in blocks[0]["text"].lower()


def test_resource_list_and_read_exact():
    d = MCPDispatcher(resources=resource_registry)
    uris = {r["uri"] for r in d.list_resources()}
    assert "greeting://hello" in uris

    contents = run(d.read_resource("greeting://hello", user=None))
    assert json.loads(contents[0]["text"]) == {"text": "hello"}


def test_resource_template_match():
    d = MCPDispatcher(resources=resource_registry)
    contents = run(d.read_resource("product://42", user=None))
    assert json.loads(contents[0]["text"]) == {"pk": "42"}


def test_read_unknown_resource_raises():
    from django_mcp_kit.errors import MCPError

    d = MCPDispatcher(resources=resource_registry)
    with pytest.raises(MCPError):
        run(d.read_resource("nope://missing", user=None))
