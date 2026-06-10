"""Registries + autodiscovery.

Tools/resources self-register on app load by being defined in an app's
``mcp_tools.py`` -- the same pattern as ``admin.py`` / ``wagtail_hooks.py``.
"""

from __future__ import annotations

from django.utils.module_loading import autodiscover_modules


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        """Register a ``Tool`` instance or class (idempotent by ``name``)."""
        if isinstance(tool, type):
            tool = tool()
        if not getattr(tool, "name", None):
            raise ValueError(f"Tool {tool!r} has no name")
        self._tools[tool.name] = tool
        return tool

    def unregister(self, name):
        self._tools.pop(name, None)

    def get(self, name):
        return self._tools.get(name)

    def all(self, *, include_disabled=False):
        """Registered tools, honouring each tool's ``enabled`` gate."""
        return [
            t for t in self._tools.values()
            if include_disabled or t.is_enabled()
        ]

    def clear(self):
        self._tools.clear()


class ResourceRegistry:
    def __init__(self):
        self._resources = {}

    def register(self, resource):
        if isinstance(resource, type):
            resource = resource()
        if not getattr(resource, "uri", None):
            raise ValueError(f"Resource {resource!r} has no uri")
        self._resources[resource.uri] = resource
        return resource

    def unregister(self, uri):
        self._resources.pop(uri, None)

    def get(self, uri):
        return self._resources.get(uri)

    def all(self):
        return list(self._resources.values())

    def clear(self):
        self._resources.clear()


# Module-level singletons -- the public registry surface.
tool_registry = ToolRegistry()
resource_registry = ResourceRegistry()


def autodiscover():
    """Import every installed app's ``mcp_tools`` module so its tools register."""
    autodiscover_modules("mcp_tools")
