"""Exception taxonomy for django-mcp-kit.

Tools (and the service functions they delegate to) raise these; :class:`MCPDispatcher`
catches them and turns them into MCP tool errors / JSON-RPC errors.

``status`` is kept for parity with the HTTP service layer (and so a ``ServiceError``
from an existing app maps cleanly via :func:`from_service_error`). ``code`` is the
JSON-RPC error code used when the failure is a protocol-level error rather than a
tool execution error.
"""

from __future__ import annotations

# JSON-RPC 2.0 reserved error codes (see the MCP spec / JSON-RPC spec).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MCPError(Exception):
    """Base class for tool/dispatch failures.

    ``detail``  human-readable message surfaced to the client.
    ``status``  HTTP-style code (parity with the service layer; not sent on the wire).
    ``code``    JSON-RPC error code for protocol-level failures.
    ``extra``   extra keys merged into the error payload.
    """

    status = 400
    code = INTERNAL_ERROR

    def __init__(self, detail, *, status=None, code=None, extra=None):
        super().__init__(detail)
        self.detail = detail
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code
        self.extra = extra or {}

    @property
    def message(self):
        """Full message including any ``extra`` context ."""
        return f"{self.detail} {self.extra}" if self.extra else self.detail


class BadRequest(MCPError):
    status = 400
    code = INVALID_PARAMS


class NotFound(MCPError):
    status = 404
    code = INVALID_PARAMS


class PermissionDenied(MCPError):
    status = 403
    code = INVALID_REQUEST


class RateLimited(MCPError):
    status = 429
    code = INVALID_REQUEST


class Invalid(MCPError):
    """Validation failure (422). Carries an ``errors`` dict in ``extra``."""

    status = 422
    code = INVALID_PARAMS

    def __init__(self, detail, *, errors=None, **kwargs):
        extra = kwargs.pop("extra", {}) or {}
        if errors is not None:
            extra = {"errors": errors, **extra}
        super().__init__(detail, extra=extra, **kwargs)


class NotAuthenticated(MCPError):
    status = 401
    code = INVALID_REQUEST


def from_service_error(exc):
    """Adapt a duck-typed service error (``detail``/``status``/``extra``) to an
    :class:`MCPError`, so apps that already raise service-style errors map
    cleanly without importing this package in their service layer."""
    if isinstance(exc, MCPError):
        return exc
    detail = getattr(exc, "detail", str(exc))
    status = getattr(exc, "status", 400)
    extra = getattr(exc, "extra", None)
    return MCPError(detail, status=status, extra=extra)
