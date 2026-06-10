"""django-mcp-kit -- turn Django/Wagtail code into MCP tools for Claude clients.

Public API: import tools, schema, permissions, and the registry from here.
"""

from .errors import (
    BadRequest,
    Invalid,
    MCPError,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    RateLimited,
)
from .permissions import AllowAny, BasePermission, HasDjangoPerm, IsAuthenticated
from .registry import resource_registry, tool_registry
from .registry import tool_registry as registry
from .resources import Resource, resource
from .schema import Schema
from .tools import Content, Image, RateLimitedMixin, Tool, tool

__all__ = [
    "Tool",
    "tool",
    "Schema",
    "Image",
    "Content",
    "RateLimitedMixin",
    "Resource",
    "resource",
    "registry",
    "tool_registry",
    "resource_registry",
    "BasePermission",
    "AllowAny",
    "IsAuthenticated",
    "HasDjangoPerm",
    "MCPError",
    "BadRequest",
    "NotFound",
    "PermissionDenied",
    "RateLimited",
    "Invalid",
    "NotAuthenticated",
]

default_app_config = "django_mcp_kit.apps.DjangoMCPKitConfig"
