"""The transport-neutral MCP dispatcher.

``MCPDispatcher`` owns ``initialize`` / ``tools.list`` / ``tools.call`` and the
resource methods. It imports **no transport and no MCP SDK** -- transports drive it
by calling these coroutines and the dispatcher hands back plain dicts. User
resolution, permission checks, sync/async execution, and result/error formatting all
live here in one reusable loop.

The authenticated ``user`` is resolved by the transport/auth layer and passed in;
the dispatcher never authenticates.
"""

from __future__ import annotations

import inspect

from asgiref.sync import sync_to_async

from . import conf
from .errors import MCPError, PermissionDenied, from_service_error
from .registry import resource_registry, tool_registry
from .resources import match_uri
from .tools import Content, Image

PROTOCOL_VERSION = "2025-06-18"


def _instantiate(perm):
    """Permission entries may be classes or instances; normalise to instances."""
    return perm() if isinstance(perm, type) else perm


def _content_block(value):
    """Map a tool's return value to an MCP content block (rich output)."""
    if isinstance(value, Image):
        return {"type": "image", "data": value.data, "mimeType": f"image/{value.format}"}
    if isinstance(value, Content):
        return {"type": "blob", "blob": value.data, "mimeType": value.mime_type}
    if isinstance(value, str):
        return {"type": "text", "text": value}
    # Default: JSON-serialise into a text block (clients parse it back).
    import json

    return {"type": "text", "text": json.dumps(value, default=str)}


class MCPDispatcher:
    def __init__(self, *, tools=None, resources=None):
        self.tools = tools or tool_registry
        self.resources = resources or resource_registry

    # -- initialize ------------------------------------------------------------
    def initialize(self):
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {
                "name": conf.get_setting("SERVER_NAME"),
                "version": conf.get_setting("SERVER_VERSION"),
            },
            "capabilities": {"tools": {"listChanged": False}, "resources": {}},
        }

    # -- tools -----------------------------------------------------------------
    def list_tools(self):
        out = []
        for tool in self.tools.all():
            entry = {
                "name": tool.name,
                "description": tool.get_description(),
                "inputSchema": tool.get_input_schema(),
            }
            output_schema = tool.get_output_schema()
            if output_schema is not None:
                entry["outputSchema"] = output_schema
            out.append(entry)
        return out

    async def call_tool(self, name, arguments=None, *, user=None):
        """Validate args -> check permissions -> run -> format result.

        Returns ``(content_blocks, is_error)`` so a transport can build either a
        normal or error tool result without re-deriving the shape.
        """
        tool = self.tools.get(name)
        if tool is None or not tool.is_enabled():
            return [self._error_text(f"Unknown tool: {name}")], True

        try:
            kwargs = self._validate(tool, arguments)
            # Permission classes may hit the ORM (user.has_perm, Wagtail
            # permissions_for_user), so run them off the event loop too.
            await sync_to_async(self._check_permissions, thread_sensitive=True)(tool, user, kwargs)
            await self._maybe_async(tool.pre_run, user, **kwargs)
            result = await self._maybe_async(tool.run, user, **kwargs)
        except MCPError as exc:
            return [self._error_text(exc.message)], True
        except Exception as exc:  # service-layer / unexpected errors
            return [self._error_text(from_service_error(exc).message)], True

        return [_content_block(result)], False

    # -- resources -------------------------------------------------------------
    def list_resources(self):
        out = []
        for res in self.resources.all():
            entry = {
                "uri": res.uri,
                "name": res.get_name(),
                "description": res.get_description(),
                "mimeType": res.mime_type,
            }
            out.append(entry)
        return out

    async def read_resource(self, uri, *, user=None):
        res, params = self._resolve_resource(uri)
        if res is None:
            raise from_service_error(MCPError(f"Unknown resource: {uri}", status=404))
        await sync_to_async(self._check_permissions, thread_sensitive=True)(res, user, params)
        value = await self._maybe_async(res.read, user, **params)
        block = _content_block(value)
        text = block.get("text", "")
        return [{"uri": uri, "mimeType": res.mime_type, "text": text}]

    # -- internals -------------------------------------------------------------
    def _validate(self, tool, arguments):
        return tool.validate(arguments)

    def _check_permissions(self, obj, user, kwargs):
        for perm in getattr(obj, "permission_classes", []):
            perm = _instantiate(perm)
            if not perm.has_permission(user, obj, **kwargs):
                raise PermissionDenied(getattr(perm, "message", "Permission denied."))

    def _resolve_resource(self, uri):
        # Exact match first, then template match.
        exact = self.resources.get(uri)
        if exact is not None:
            return exact, {}
        for res in self.resources.all():
            if res.is_template:
                params = match_uri(res.uri, uri)
                if params is not None:
                    return res, params
        return None, {}

    async def _maybe_async(self, fn, *args, **kwargs):
        """Run a tool hook/body: await if async, else off-loop via sync_to_async
        (so Django's ORM is safe)."""
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        return await sync_to_async(fn, thread_sensitive=True)(*args, **kwargs)

    def _error_text(self, message):
        return {"type": "text", "text": message}
