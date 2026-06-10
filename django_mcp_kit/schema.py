"""Input/Output schema generation.

Three sources, in declaration order:

1. A ``Tool`` subclass's ``Input`` pydantic model.
2. A plain ``@tool`` function -> type-hint introspection, by synthesising a pydantic
   model from the signature.
3. A DRF serializer -> JSON Schema -- see :mod:`django_mcp_kit.drf`.

We lean on pydantic for correctness rather than hand-rolling an introspector.
"""

from __future__ import annotations

import inspect

from pydantic import BaseModel, create_model


class Schema(BaseModel):
    """Base class for a tool's ``Input`` / ``Output`` model.

    Thin alias over :class:`pydantic.BaseModel` so app code imports it from us
    (``from django_mcp_kit import Schema``) and never needs pydantic directly.
    """


def json_schema(model):
    """JSON Schema dict for a pydantic model class (for ``tools/list``)."""
    if model is None:
        return {"type": "object", "properties": {}}
    return model.model_json_schema()


def validate(model, arguments):
    """Validate raw ``arguments`` against ``model``; return a plain kwargs dict.

    Raises :class:`pydantic.ValidationError`; the dispatcher maps that to an
    ``Invalid`` MCP error.
    """
    if model is None:
        return dict(arguments or {})
    instance = model.model_validate(arguments or {})
    return {name: getattr(instance, name) for name in model.model_fields}


# Parameters that are injected by the dispatcher, not part of the wire schema.
INJECTED_PARAMS = {"self", "user", "ctx", "context"}


def model_from_callable(func, *, name=None):
    """Synthesise a pydantic model from a function's type-hinted signature.

    Skips dispatcher-injected params (``self``/``user``/``ctx``). A parameter with
    no annotation is typed ``Any``; one with no default is required.
    """
    sig = inspect.signature(func)
    fields = {}
    for pname, param in sig.parameters.items():
        if pname in INJECTED_PARAMS:
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = param.annotation if param.annotation is not param.empty else object
        default = param.default if param.default is not param.empty else ...
        fields[pname] = (annotation, default)
    model_name = name or f"{getattr(func, '__name__', 'Tool').title()}Input"
    return create_model(model_name, __base__=Schema, **fields)
