"""Native-authz tests.

The library has no Wagtail dependency: object-level permission checks live inside the
tool body / service function. These tests verify the contract the library *does* own:
the resolved ``user`` reaches ``run()``, an object-level ``permissions_for_user`` check
in the body gates execution, and a ``PermissionDenied`` raised there maps to a tool error.
A fake page stands in for a Wagtail ``Page`` so no Wagtail install is needed.
"""

import asyncio
import json

import pytest

from django_mcp_kit import HasDjangoPerm, PermissionDenied, Schema, Tool
from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.registry import ToolRegistry


def run(coro):
    return asyncio.run(coro)


def make_dispatcher(*tool_classes):
    reg = ToolRegistry()
    for tc in tool_classes:
        reg.register(tc())
    return MCPDispatcher(tools=reg)


# --- Wagtail-style object permissions, simulated -----------------------------
class _FakePagePerms:
    def __init__(self, can_edit, can_publish=False):
        self._can_edit = can_edit
        self._can_publish = can_publish

    def can_edit(self):
        return self._can_edit

    def can_publish(self):
        return self._can_publish


class _FakePage:
    """Stands in for a Wagtail Page exposing permissions_for_user()."""

    def __init__(self, user_can_edit):
        # Map username -> allowed, mimicking real per-user permission resolution.
        self._allowed = user_can_edit

    def permissions_for_user(self, user):
        allowed = self._allowed.get(getattr(user, "username", None), False)
        return _FakePagePerms(can_edit=allowed)


class EditPageTool(Tool):
    """An object-permission check inside a tool body (Wagtail-style)."""

    abstract = True
    name = "edit_page"

    class Input(Schema):
        pass

    # Injected per-test so we can flip who is allowed.
    page = None

    def run(self, user):
        if not self.page.permissions_for_user(user).can_edit():
            raise PermissionDenied("You do not have permission to edit this page.")
        return {"edited": True}


class _User:
    def __init__(self, username):
        self.username = username
        self.is_active = True


def test_wagtail_object_permission_allows():
    tool = EditPageTool()
    tool.page = _FakePage({"alice": True})
    d = MCPDispatcher(tools=ToolRegistry())
    d.tools.register(tool)

    blocks, is_error = run(d.call_tool("edit_page", {}, user=_User("alice")))
    assert is_error is False
    assert json.loads(blocks[0]["text"]) == {"edited": True}


def test_wagtail_object_permission_denies():
    tool = EditPageTool()
    tool.page = _FakePage({"alice": True})  # bob not listed -> denied
    d = MCPDispatcher(tools=ToolRegistry())
    d.tools.register(tool)

    blocks, is_error = run(d.call_tool("edit_page", {}, user=_User("bob")))
    assert is_error is True
    assert "permission to edit this page" in blocks[0]["text"]


# --- Native Django model permissions via HasDjangoPerm -----------------------
class ChangeProductTool(Tool):
    abstract = True
    name = "change_product"
    permission_classes = [HasDjangoPerm("dummyapp.change_product")]

    class Input(Schema):
        pass

    def run(self, user):
        return {"changed": True}


@pytest.mark.django_db(transaction=True)
def test_has_django_perm_denied_then_allowed():
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission

    User = get_user_model()
    user = User.objects.create(username="editor", is_active=True)

    d = make_dispatcher(ChangeProductTool)

    # No permission yet -> denied by the permission_class (before run()).
    blocks, is_error = run(d.call_tool("change_product", {}, user=user))
    assert is_error is True

    perm = Permission.objects.get(
        codename="change_product", content_type__app_label="dummyapp"
    )
    user.user_permissions.add(perm)
    # Re-fetch to clear the per-instance permission cache.
    user = User.objects.get(pk=user.pk)

    blocks, is_error = run(d.call_tool("change_product", {}, user=user))
    assert is_error is False
    assert json.loads(blocks[0]["text"]) == {"changed": True}
