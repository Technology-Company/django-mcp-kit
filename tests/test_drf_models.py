import asyncio
import json

import pytest

pytest.importorskip("rest_framework")

from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.drf import register_drf_viewset
from django_mcp_kit.models import ModelToolset
from django_mcp_kit.registry import ResourceRegistry, ToolRegistry

from tests.dummyapp.api import ProductReadOnlyViewSet, ProductViewSet
from tests.dummyapp.models import Product


def run(coro):
    return asyncio.run(coro)


def dispatcher_for(tool_classes, resources=None):
    reg = ToolRegistry()
    for tc in tool_classes:
        reg.register(tc())
    return MCPDispatcher(tools=reg, resources=resources or ResourceRegistry())


def test_readonly_viewset_two_tools():
    tools = register_drf_viewset(ProductReadOnlyViewSet, prefix="ro")
    names = {t.name for t in tools}
    assert names == {"ro_list", "ro_retrieve"}


def test_modelviewset_full_crud():
    tools = register_drf_viewset(ProductViewSet, prefix="rw")
    names = {t.name for t in tools}
    assert names == {
        "rw_list", "rw_retrieve", "rw_create",
        "rw_update", "rw_partial_update", "rw_destroy",
    }


def test_actions_subset():
    tools = register_drf_viewset(ProductViewSet, prefix="sub", actions=["list", "create"])
    assert {t.name for t in tools} == {"sub_list", "sub_create"}


def test_create_schema_from_serializer():
    tools = register_drf_viewset(ProductViewSet, prefix="sch", actions=["create"])
    d = dispatcher_for(tools)
    create = next(t for t in d.list_tools() if t["name"] == "sch_create")
    props = create["inputSchema"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["price"]["type"] == "number"
    assert props["in_stock"]["type"] == "boolean"


@pytest.mark.django_db(transaction=True)
def test_drf_list_and_retrieve_roundtrip():
    Product.objects.create(name="Widget", price=3)
    tools = register_drf_viewset(ProductReadOnlyViewSet, prefix="r1")
    d = dispatcher_for(tools)

    blocks, is_error = run(d.call_tool("r1_list", {}))
    assert is_error is False
    rows = json.loads(blocks[0]["text"])
    assert rows[0]["name"] == "Widget"

    pk = rows[0]["id"]
    blocks, is_error = run(d.call_tool("r1_retrieve", {"pk": pk}))
    assert json.loads(blocks[0]["text"])["name"] == "Widget"


@pytest.mark.django_db(transaction=True)
def test_drf_create_roundtrip():
    tools = register_drf_viewset(ProductViewSet, prefix="c1", actions=["create"])
    d = dispatcher_for(tools)
    blocks, is_error = run(d.call_tool("c1_create", {"name": "New", "price": "5.00", "in_stock": True}))
    assert is_error is False
    assert Product.objects.filter(name="New").exists()


@pytest.mark.django_db(transaction=True)
def test_drf_create_validation_error():
    tools = register_drf_viewset(ProductViewSet, prefix="c2", actions=["create"])
    d = dispatcher_for(tools)
    blocks, is_error = run(d.call_tool("c2_create", {"price": "5.00"}))  # missing name
    assert is_error is True
    assert "Validation failed" in blocks[0]["text"]


@pytest.mark.django_db(transaction=True)
def test_drf_update_partial_and_destroy_roundtrip():
    p = Product.objects.create(name="Old", price=1, in_stock=True)
    tools = register_drf_viewset(
        ProductViewSet, prefix="w1", actions=["update", "partial_update", "destroy"])
    d = dispatcher_for(tools)

    # Full update requires all writable fields.
    _, is_error = run(d.call_tool(
        "w1_update", {"pk": p.pk, "name": "Renamed", "price": "2.00", "in_stock": False}))
    assert is_error is False
    p.refresh_from_db()
    assert p.name == "Renamed" and p.in_stock is False

    # Partial update touches one field only.
    _, is_error = run(d.call_tool("w1_partial_update", {"pk": p.pk, "name": "Patched"}))
    assert is_error is False
    p.refresh_from_db()
    assert p.name == "Patched"

    # Destroy.
    _, is_error = run(d.call_tool("w1_destroy", {"pk": p.pk}))
    assert is_error is False
    assert not Product.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_drf_retrieve_not_found():
    tools = register_drf_viewset(ProductReadOnlyViewSet, prefix="nf", actions=["retrieve"])
    d = dispatcher_for(tools)
    blocks, is_error = run(d.call_tool("nf_retrieve", {"pk": 999999}))
    assert is_error is True
    assert "Not found" in blocks[0]["text"]


def test_modeltoolset_read_only_default():
    class ProductToolset(ModelToolset):
        model = Product
        prefix = "mt"

    from django_mcp_kit.registry import tool_registry
    names = {t.name for t in tool_registry.all(include_disabled=True)}
    assert "mt_list" in names and "mt_retrieve" in names
    assert "mt_create" not in names


def test_modeltoolset_resource_registration():
    class ProductToolset2(ModelToolset):
        model = Product
        prefix = "mtr"
        as_resource = True

    from django_mcp_kit.registry import resource_registry
    uris = {r.uri for r in resource_registry.all()}
    assert "mtr://{pk}" in uris


def test_modeltoolset_blocks_writes_on_wagtail_managed_model():
    class FakeWagtailModel:
        __name__ = "FakeWagtailModel"

        def save_revision(self):  # marks it as Wagtail-workflow managed
            pass

        def permissions_for_user(self, user):
            pass

    with pytest.raises(ValueError, match="Wagtail-managed"):
        class BadToolset(ModelToolset):
            model = FakeWagtailModel
            actions = ["list", "create"]  # write action triggers the guard
