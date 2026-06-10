"""Integration tests for the SDK wire transport (skipped if mcp/starlette absent)."""

import json

import pytest

pytest.importorskip("mcp")
pytest.importorskip("starlette")

from starlette.testclient import TestClient

from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.registry import ToolRegistry
from django_mcp_kit.schema import Schema
from django_mcp_kit.tools import Tool
from django_mcp_kit.transports.sdk import build_application


class PingTool(Tool):
    abstract = True
    name = "ping"
    description = "Ping."

    class Input(Schema):
        msg: str

    def run(self, user, msg):
        return {"pong": msg}


def make_app(require_auth=False):
    reg = ToolRegistry()
    reg.register(PingTool())
    dispatcher = MCPDispatcher(tools=reg)
    return build_application(dispatcher), require_auth


@pytest.fixture
def client(settings):
    settings.DJANGO_MCP_KIT = {**settings.DJANGO_MCP_KIT, "REQUIRE_AUTH": False}
    app, _ = make_app()
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_discovery_metadata(client):
    r = client.get("/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    assert r.json()["resource"] == "https://example.test/mcp"


def test_unauthorized_challenge(settings):
    settings.DJANGO_MCP_KIT = {**settings.DJANGO_MCP_KIT, "REQUIRE_AUTH": True}
    app, _ = make_app(require_auth=True)
    with TestClient(app) as c:
        r = c.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        )
        assert r.status_code == 401
        assert "resource_metadata=" in r.headers.get("WWW-Authenticate", "")


def _parse_sse(text):
    """Pull the JSON payload out of an SSE 'data:' line."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    return json.loads(text)


class ImageTool(Tool):
    abstract = True
    name = "img"
    description = "Returns an image."

    class Input(Schema):
        pass

    def run(self, user):
        from django_mcp_kit import Image
        return Image(data="Zm9v", format="png")


def test_image_content_through_transport(settings):
    settings.DJANGO_MCP_KIT = {**settings.DJANGO_MCP_KIT, "REQUIRE_AUTH": False}
    reg = ToolRegistry()
    reg.register(ImageTool())
    app = build_application(MCPDispatcher(tools=reg))
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(app) as c:
        def rpc(method, params=None, _id=1):
            r = c.post("/mcp", headers=headers, json={
                "jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}})
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[len("data:"):].strip())
            return json.loads(r.text)

        rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "t", "version": "1"}})
        called = rpc("tools/call", {"name": "img", "arguments": {}}, _id=2)
        block = called["result"]["content"][0]
        assert block["type"] == "image"
        assert block["mimeType"] == "image/png"


def test_full_handshake_and_tool_call(client):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    def rpc(method, params=None, _id=1):
        r = client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}})
        assert r.status_code == 200, r.text
        return _parse_sse(r.text)

    init = rpc("initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"}})
    assert init["result"]["serverInfo"]["name"] == "test-mcp"

    tools = rpc("tools/list", _id=2)
    names = {t["name"] for t in tools["result"]["tools"]}
    assert "ping" in names

    called = rpc("tools/call", {"name": "ping", "arguments": {"msg": "hey"}}, _id=3)
    content = called["result"]["content"]
    assert json.loads(content[0]["text"]) == {"pong": "hey"}
