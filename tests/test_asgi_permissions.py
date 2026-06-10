"""Prove ORM-backed permission checks work through the real ASGI/HTTP stack.

A tool guarded by a Django model permission is called over the SDK transport via
Starlette's TestClient (a real event loop), with a bearer token resolving to a real
DB user. This is the path a live uvicorn deployment uses, so it confirms permission
checks (which touch the ORM) run correctly under ASGI -- not just in the dispatcher.
"""

import json

import pytest

pytest.importorskip("mcp")
pytest.importorskip("starlette")

from starlette.testclient import TestClient

from django_mcp_kit import HasDjangoPerm, Schema, Tool
from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.registry import ToolRegistry
from django_mcp_kit.transports.sdk import build_application


class ChangeProduct(Tool):
    abstract = True
    name = "change_product"
    permission_classes = [HasDjangoPerm("dummyapp.change_product")]

    class Input(Schema):
        pass

    def run(self, user):
        return {"changed_by": user.username}


def _rpc(client, method, params=None, _id=1):
    r = client.post(
        "/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": "Bearer editor",  # resolves to the DB user 'editor'
        },
        json={"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}},
    )
    assert r.status_code == 200, r.text
    for line in r.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    return json.loads(r.text)


@pytest.mark.django_db(transaction=True)
def test_orm_permission_over_asgi(settings):
    settings.DJANGO_MCP_KIT = {
        **settings.DJANGO_MCP_KIT,
        "REQUIRE_AUTH": True,
        "AUTH_BACKENDS": ["django_mcp_kit.auth.StaticBearer"],
        "STATIC_BEARER_RESOLVER": "tests.dummyapp.tokens:user_for_token_db",
    }

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission

    User = get_user_model()
    User.objects.create(username="editor", is_active=True)

    reg = ToolRegistry()
    reg.register(ChangeProduct())
    app = build_application(MCPDispatcher(tools=reg))

    with TestClient(app) as client:
        _rpc(client, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"}})

        # No permission yet -> denied (the ORM-backed check runs under ASGI).
        denied = _rpc(client, "tools/call",
                      {"name": "change_product", "arguments": {}}, _id=2)
        assert denied["result"]["isError"] is True

        # Grant the permission, then it succeeds over the same HTTP stack.
        perm = Permission.objects.get(
            codename="change_product", content_type__app_label="dummyapp")
        User.objects.get(username="editor").user_permissions.add(perm)

        allowed = _rpc(client, "tools/call",
                       {"name": "change_product", "arguments": {}}, _id=3)
        assert allowed["result"]["isError"] is False
        assert json.loads(allowed["result"]["content"][0]["text"]) == {"changed_by": "editor"}
