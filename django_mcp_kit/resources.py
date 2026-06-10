"""MCP Resources.

Mirrors the ``Tool`` / ``@tool`` pair: a ``Resource`` subclass or a ``@resource``
decorated function, addressable by a URI (optionally a ``scheme://{param}`` template).
"""

from __future__ import annotations

import inspect
import re


def compile_template(uri):
    """Turn ``"category://{slug}"`` into a compiled regex capturing ``slug``.

    A URI with no ``{param}`` placeholders compiles to an exact match.
    """
    param_names = re.findall(r"\{(\w+)\}", uri)
    pattern = re.escape(uri)
    for pname in param_names:
        pattern = pattern.replace(re.escape("{" + pname + "}"), rf"(?P<{pname}>[^/]+)")
    return re.compile(f"^{pattern}$"), param_names


def match_uri(template, uri):
    """Match a concrete ``uri`` against a ``template``; return params dict or None."""
    regex, _ = compile_template(template)
    m = regex.match(uri)
    return m.groupdict() if m else None


class Resource:
    """Base class for a read-addressable MCP resource."""

    uri = None
    name = None
    description = ""
    mime_type = "application/json"
    permission_classes = []
    abstract = True

    def __init_subclass__(cls, abstract=False, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.abstract = abstract or cls.__dict__.get("abstract", False)
        if cls.abstract or not getattr(cls, "uri", None):
            return
        from .registry import resource_registry
        resource_registry.register(cls())

    @property
    def is_template(self):
        return "{" in (self.uri or "")

    def get_name(self):
        return self.name or self.uri

    def get_description(self):
        if self.description:
            return self.description
        return (self.read.__doc__ or "").strip()

    def read(self, user, **params):  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def is_async(self):
        return inspect.iscoroutinefunction(self.read)


def resource(uri, name=None, description=None, permission_classes=None):
    """Decorator sugar: wrap a function into a ``Resource`` subclass."""

    def decorator(func):
        from .tools import _invoke

        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            async def read(self, user, **params):
                return await _invoke(func, user, params)
        else:
            def read(self, user, **params):
                return _invoke(func, user, params)

        attrs = {
            "uri": uri,
            "name": name or func.__name__,
            "description": description or (func.__doc__ or "").strip(),
            "permission_classes": list(permission_classes or []),
            "read": read,
            "__module__": getattr(func, "__module__", __name__),
            "__doc__": func.__doc__,
        }
        return type(func.__name__, (Resource,), attrs)

    return decorator
