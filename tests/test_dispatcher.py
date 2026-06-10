import asyncio
import json

import pytest

from django_mcp_kit.dispatcher import MCPDispatcher
from django_mcp_kit.registry import ToolRegistry
from django_mcp_kit.tools import Image, Tool
from django_mcp_kit.schema import Schema


def run(coro):
    return asyncio.run(coro)


def make_dispatcher(*tool_classes):
    reg = ToolRegistry()
    for tc in tool_classes:
        reg.register(tc())
    return MCPDispatcher(tools=reg)


# -- fixtures: tools defined abstract so they don't touch the global registry ----
class EchoTool(Tool):
    abstract = True
    name = "echo"
    description = "Echo."

    class Input(Schema):
        message: str

    def run(self, user, message):
        return {"echo": message}


class AsyncTool(Tool):
    abstract = True
    name = "aecho"

    class Input(Schema):
        x: int

    async def run(self, user, x):
        return {"x": x}


class ImageTool(Tool):
    abstract = True
    name = "img"

    class Input(Schema):
        pass

    def run(self, user):
        return Image(data="Zm9v", format="png")


def test_initialize():
    d = make_dispatcher()
    info = d.initialize()
    assert info["serverInfo"]["name"] == "test-mcp"
    assert "tools" in info["capabilities"]


def test_list_tools_schema():
    d = make_dispatcher(EchoTool)
    tools = d.list_tools()
    assert len(tools) == 1
    entry = tools[0]
    assert entry["name"] == "echo"
    assert entry["inputSchema"]["properties"]["message"]["type"] == "string"
    assert "message" in entry["inputSchema"]["required"]


def test_call_tool_happy_path():
    d = make_dispatcher(EchoTool)
    blocks, is_error = run(d.call_tool("echo", {"message": "hi"}))
    assert is_error is False
    assert json.loads(blocks[0]["text"]) == {"echo": "hi"}


def test_call_tool_async_body():
    d = make_dispatcher(AsyncTool)
    blocks, is_error = run(d.call_tool("aecho", {"x": 5}))
    assert is_error is False
    assert json.loads(blocks[0]["text"]) == {"x": 5}


def test_call_tool_invalid_args():
    d = make_dispatcher(EchoTool)
    blocks, is_error = run(d.call_tool("echo", {}))  # missing required 'message'
    assert is_error is True
    assert "Invalid tool arguments" in blocks[0]["text"]


def test_call_unknown_tool():
    d = make_dispatcher(EchoTool)
    blocks, is_error = run(d.call_tool("nope", {}))
    assert is_error is True
    assert "Unknown tool" in blocks[0]["text"]


def test_image_content_block():
    d = make_dispatcher(ImageTool)
    blocks, is_error = run(d.call_tool("img", {}))
    assert is_error is False
    assert blocks[0]["type"] == "image"
    assert blocks[0]["mimeType"] == "image/png"
