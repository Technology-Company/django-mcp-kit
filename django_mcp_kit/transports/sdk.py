"""Official-SDK wire transport (the default wire transport).

The **only** SDK-coupled module. It drives our transport-neutral
:class:`~django_mcp_kit.dispatcher.MCPDispatcher` from the SDK's low-level server +
Streamable-HTTP session manager. Nothing in tools/logic/auth/dispatch imports the SDK;
swapping this for ``transports/http.py`` later is a contained change.

Auth is *ours*: an ASGI middleware resolves the Django user via the
``Authenticator`` chain and stashes it in a context var the tool handler reads.
``mcp`` is imported lazily so the SDK stays contained to this module.
"""

from __future__ import annotations

import base64
import contextvars
import json

from asgiref.sync import sync_to_async
from django.conf import settings

from .. import conf
from ..auth import authenticate_request, protected_resource_metadata
from ..dispatcher import MCPDispatcher

_current_user = contextvars.ContextVar("django_mcp_kit_user", default=None)


def _convert_block(block):
    import mcp.types as types

    kind = block.get("type")
    if kind == "image":
        data = block["data"]
        if isinstance(data, (bytes, bytearray)):
            data = base64.b64encode(data).decode("ascii")
        return types.ImageContent(type="image", data=data, mimeType=block["mimeType"])
    if kind == "text":
        return types.TextContent(type="text", text=block["text"])
    return types.TextContent(type="text", text=json.dumps(block, default=str))


def build_server(dispatcher):
    """Build the SDK low-level server whose handlers delegate to the dispatcher."""
    import mcp.types as types
    from mcp.server.lowlevel import Server

    server = Server(conf.get_setting("SERVER_NAME"), version=conf.get_setting("SERVER_VERSION"))

    @server.list_tools()
    async def _list_tools():
        out = []
        for entry in dispatcher.list_tools():
            kwargs = {
                "name": entry["name"],
                "description": entry["description"],
                "inputSchema": entry["inputSchema"],
            }
            if entry.get("outputSchema"):
                kwargs["outputSchema"] = entry["outputSchema"]
            out.append(types.Tool(**kwargs))
        return out

    # validate_input=False: our dispatcher owns validation + error formatting.
    @server.call_tool(validate_input=False)
    async def _call_tool(name, arguments):
        blocks, is_error = await dispatcher.call_tool(name, arguments, user=_current_user.get())
        return types.CallToolResult(content=[_convert_block(b) for b in blocks], isError=is_error)

    @server.list_resources()
    async def _list_resources():
        return [
            types.Resource(
                uri=entry["uri"],
                name=entry["name"],
                description=entry["description"],
                mimeType=entry["mimeType"],
            )
            for entry in dispatcher.list_resources()
            if "{" not in entry["uri"]  # templates are advertised separately
        ]

    @server.read_resource()
    async def _read_resource(uri):
        contents = await dispatcher.read_resource(str(uri), user=_current_user.get())
        return contents[0]["text"] if contents else ""

    return server


def _transport_security():
    """Build TransportSecuritySettings (opt-in, off by default)."""
    from mcp.server.transport_security import TransportSecuritySettings

    if not conf.get_setting("DNS_REBINDING_PROTECTION", False):
        # Off must be explicit (the class default is True).
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    # On must populate hosts (empty allowlist rejects everything).
    hosts = [h for h in getattr(settings, "ALLOWED_HOSTS", []) if h and h != "*"]
    origins = [f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


class _ScopeRequest:
    """Minimal request shim exposing case-insensitive headers from an ASGI scope."""

    def __init__(self, scope):
        self.headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}


async def _send_json(send, status, payload, extra_headers=None):
    body = json.dumps(payload).encode()
    raw_headers = [(b"content-type", b"application/json")]
    for key, value in (extra_headers or {}).items():
        raw_headers.append((key.encode(), value.encode()))
    await send({"type": "http.response.start", "status": status, "headers": raw_headers})
    await send({"type": "http.response.body", "body": body})


def build_application(dispatcher=None, *, mcp_path="/mcp"):
    """Build the standalone MCP ASGI app.

    A small hand-rolled ASGI router (rather than a Starlette ``Mount``, which would
    301/307-redirect a bare ``/mcp`` to ``/mcp/``) so the wire endpoint answers at
    ``/mcp`` directly. Routes:
      * ``GET /healthz`` -- liveness probe (singleserver/systemd point here)
      * ``GET /.well-known/oauth-protected-resource`` -- RFC 9728 metadata
      * ``/mcp`` (any method) -- auth (ours) -> Streamable-HTTP wire
    """
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    dispatcher = dispatcher or MCPDispatcher()
    server = build_server(dispatcher)
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=False,
        stateless=bool(conf.get_setting("STATELESS", True)),
        security_settings=_transport_security(),
    )
    require_auth = bool(conf.get_setting("REQUIRE_AUTH", True))
    state = {}

    async def handle_mcp(scope, receive, send):
        # Auth backends hit the ORM (token->user lookup), so resolve off the event loop.
        user, challenge = await sync_to_async(authenticate_request, thread_sensitive=True)(
            _ScopeRequest(scope)
        )
        if user is None and require_auth:
            status, headers = challenge
            await _send_json(send, status, {"error": "unauthorized"}, headers)
            return
        token = _current_user.set(user)
        try:
            await session_manager.handle_request(scope, receive, send)
        finally:
            _current_user.reset(token)

    async def lifespan(scope, receive, send):
        # Run the session manager's task group for the lifetime of the app.
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                cm = session_manager.run()
                await cm.__aenter__()
                state["cm"] = cm
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                cm = state.pop("cm", None)
                if cm is not None:
                    await cm.__aexit__(None, None, None)
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def application(scope, receive, send):
        kind = scope["type"]
        if kind == "lifespan":
            await lifespan(scope, receive, send)
            return
        if kind != "http":
            return
        path = scope.get("path", "")
        if path == "/healthz":
            await _send_json(send, 200, {"status": "ok"})
        elif path == "/.well-known/oauth-protected-resource":
            await _send_json(send, 200, protected_resource_metadata())
        elif path == mcp_path or path.startswith(mcp_path + "/"):
            await handle_mcp(scope, receive, send)
        else:
            await _send_json(send, 404, {"error": "not found"})

    return application
