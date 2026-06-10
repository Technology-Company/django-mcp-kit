"""ASGI entrypoints.

``get_application()`` builds the standalone MCP ASGI app from the configured transport
(``DJANGO_MCP_KIT["TRANSPORT"]``). ``mount()`` composes the MCP app beside an existing
Django ASGI app for the co-located topology (A).
"""

from __future__ import annotations

from importlib import import_module

from . import conf


def get_application(dispatcher=None):
    """Build the MCP ASGI app from the configured transport module."""
    module = import_module(conf.get_setting("TRANSPORT"))
    return module.build_application(dispatcher)


def mount(django_asgi_app, prefix="/mcp"):
    """Route ``prefix`` (and the MCP app's discovery/health) to the MCP app, and
    everything else to ``django_asgi_app`` (topology A -- one ASGI process).

    The combined app forwards the ASGI ``lifespan`` to the MCP app so the
    Streamable-HTTP session manager starts; HTTP requests are dispatched by path.
    """
    mcp_app = get_application()
    mcp_paths = (prefix, "/healthz", "/.well-known/oauth-protected-resource")

    async def application(scope, receive, send):
        if scope["type"] == "lifespan":
            await mcp_app(scope, receive, send)
            return
        path = scope.get("path", "")
        if any(path == p or path.startswith(p + "/") or path.startswith(prefix) for p in mcp_paths):
            await mcp_app(scope, receive, send)
        else:
            await django_asgi_app(scope, receive, send)

    return application
