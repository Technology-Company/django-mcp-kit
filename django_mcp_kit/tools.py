"""The ``Tool`` base class, mixins, the ``@tool`` decorator, and rich-content types.

Tools are *classes* (the Django/DRF idiom) carrying declarative metadata; ``run()``
is the body and may be sync or async. A subclass self-registers on definition
(``__init_subclass__``) unless it is ``abstract`` (mixins / shared bases) or has no
``name``.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from . import conf
from .errors import RateLimited
from .schema import json_schema, model_from_callable


@dataclass
class Image:
    """Rich image content returned from ``run()`` (maps to an MCP image block).

    For binary/image results; app code imports it from us, never from the MCP SDK.
    """

    data: bytes | str
    format: str = "png"


@dataclass
class Content:
    """Generic non-JSON content block (``mime_type`` + bytes/text)."""

    data: bytes | str
    mime_type: str


class Tool:
    """Base class for MCP tools.

    Class attributes:
        ``name``               unique tool name (required to register).
        ``description``        human/LLM-facing description (defaults to the docstring).
        ``permission_classes`` DRF-style permissions checked before ``run()``.
        ``Input`` / ``Output`` optional pydantic ``Schema`` subclasses.
        ``enabled``            optional zero-arg callable; tool is hidden when it
                               returns falsy (the ``MCP_ALLOW_PUBLISH`` pattern).
    """

    name = None
    description = ""
    permission_classes = []
    Input = None
    Output = None
    enabled = None
    abstract = True  # the base itself never registers

    def __init_subclass__(cls, abstract=False, **kwargs):
        super().__init_subclass__(**kwargs)
        # A subclass is concrete unless flagged abstract or missing a name.
        cls.abstract = abstract or cls.__dict__.get("abstract", False)
        if cls.abstract or not getattr(cls, "name", None):
            return
        from .registry import tool_registry
        tool_registry.register(cls())

    # -- description -----------------------------------------------------------
    def get_description(self):
        if self.description:
            return self.description
        return (self.run.__doc__ or "").strip()

    # -- schema ----------------------------------------------------------------
    def input_model(self):
        """The pydantic model used to validate inputs (Input attr or run() hints)."""
        if self.Input is not None:
            return self.Input
        return model_from_callable(self.run, name=f"{type(self).__name__}Input")

    def get_input_schema(self):
        return json_schema(self.input_model())

    def validate(self, arguments):
        """Validate raw ``arguments`` -> kwargs for ``run()``.

        Default uses the pydantic ``input_model``; DRF-backed tools override this to
        validate via a serializer. Must raise ``Invalid`` (an ``MCPError``) on failure.
        """
        from pydantic import ValidationError

        from .errors import Invalid
        from .schema import validate as _validate

        try:
            return _validate(self.input_model(), arguments or {})
        except ValidationError as exc:
            raise Invalid("Invalid tool arguments.", errors=exc.errors(include_url=False))

    def get_output_schema(self):
        return json_schema(self.Output) if self.Output is not None else None

    # -- gating ----------------------------------------------------------------
    def is_enabled(self):
        """Evaluate the ``enabled`` gate (raw class attr, called with no args)."""
        for klass in type(self).__mro__:
            if "enabled" in klass.__dict__:
                fn = klass.__dict__["enabled"]
                return True if fn is None else bool(fn())
        return True

    # -- execution hooks -------------------------------------------------------
    def pre_run(self, user, **kwargs):
        """Hook run after permission checks, before ``run()``. Override in mixins."""

    def run(self, user, **kwargs):  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def is_async(self):
        return inspect.iscoroutinefunction(self.run)


class RateLimitedMixin:
    """Per-user fixed-window write throttle.

    Compose ahead of ``Tool``: ``class PatchBlock(RateLimitedMixin, Tool): ...``.
    Defaults come from ``DJANGO_MCP_KIT["WRITE_RATE_LIMIT"]`` = (count, window_secs).
    """

    abstract = True
    rate_limit = None  # (count, window) override; else uses the setting

    def pre_run(self, user, **kwargs):
        super().pre_run(user, **kwargs)
        from django.core.cache import cache

        limit, window = self.rate_limit or conf.get_setting("WRITE_RATE_LIMIT", (30, 60))
        key = f"django_mcp_kit:writes:{getattr(user, 'pk', 'anon')}"
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, window)
            count = 1
        if count > limit:
            raise RateLimited("Write rate limit exceeded. Try again shortly.", extra={"limit": limit})


def _invoke(func, user, kwargs):
    """Call ``func`` passing ``user`` only if it declares the parameter."""
    sig = inspect.signature(func)
    call = {}
    params = sig.parameters
    if "user" in params:
        call["user"] = user
    accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in params.values())
    for key, value in kwargs.items():
        if accepts_kwargs or key in params:
            call[key] = value
    return func(**call)


def tool(name=None, description=None, permission_classes=None, enabled=None):
    """Decorator sugar: wrap a function into a ``Tool`` subclass.

    The wrapped function may take ``user`` and any input params; it may be sync or
    async. Input schema is derived from its type hints.
    """

    def decorator(func):
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            async def run(self, user, **kwargs):
                return await _invoke(func, user, kwargs)
        else:
            def run(self, user, **kwargs):
                return _invoke(func, user, kwargs)

        attrs = {
            "name": name or func.__name__,
            "description": description or (func.__doc__ or "").strip(),
            "permission_classes": list(permission_classes or []),
            "Input": model_from_callable(func, name=f"{func.__name__.title()}Input"),
            "run": run,
            "__module__": getattr(func, "__module__", __name__),
            "__doc__": func.__doc__,
        }
        if enabled is not None:
            attrs["enabled"] = staticmethod(enabled)
        # Building the subclass auto-registers it (see Tool.__init_subclass__).
        return type(func.__name__, (Tool,), attrs)

    return decorator
