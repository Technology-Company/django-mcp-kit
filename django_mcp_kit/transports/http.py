"""Own Streamable-HTTP transport (not yet implemented).

Because the dispatcher is transport-neutral, replacing the SDK wire with our own
JSON-RPC / Streamable-HTTP view is a contained swap, not a rewrite. Not yet
implemented; ``transports/sdk.py`` is the default.
"""

from __future__ import annotations


def build_application(dispatcher=None):  # pragma: no cover - not implemented
    raise NotImplementedError(
        "The own-wire HTTP transport is not implemented yet. Use TRANSPORT="
        "'django_mcp_kit.transports.sdk'."
    )
