"""DRF on-ramp.

``register_drf_viewset()`` adapts an existing DRF ``ViewSet`` into tools -- one per
action -- reusing the viewset's serializer (for input schema + validation), its
``queryset``/``get_queryset``, and its ``permission_classes``. A ``ReadOnlyModelViewSet``
yields ``list``/``retrieve``; a ``ModelViewSet`` yields full CRUD. This is a simple
router-level shape.

DRF is imported lazily, so it's only loaded when this module is used.
"""

from __future__ import annotations

from .errors import Invalid, NotFound, PermissionDenied
from .permissions import BasePermission
from .tools import Tool

# Standard ModelViewSet actions in a stable order.
WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}
STANDARD_ACTIONS = ["list", "retrieve", "create", "update", "partial_update", "destroy"]


def _field_type(field):
    from rest_framework import serializers as drf

    if isinstance(field, (drf.IntegerField,)):
        return "integer"
    if isinstance(field, (drf.FloatField, drf.DecimalField)):
        return "number"
    if isinstance(field, drf.BooleanField):
        return "boolean"
    if isinstance(field, (drf.ListField, drf.ListSerializer)):
        return "array"
    if isinstance(field, drf.Serializer):
        return "object"
    return "string"


def serializer_schema(serializer_class, *, all_optional=False):
    """Build a JSON Schema object from a serializer's writable fields."""
    serializer = serializer_class()
    props = {}
    required = []
    for name, field in serializer.fields.items():
        if field.read_only:
            continue
        props[name] = {"type": _field_type(field)}
        if field.required and not all_optional:
            required.append(name)
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


class _FakeRequest:
    """Minimal request for reusing DRF permission classes."""

    def __init__(self, user, method="GET"):
        self.user = user
        self.method = method
        self.auth = None


def _adapt_permission(drf_perm_class, viewset_class, method):
    class _Adapter(BasePermission):
        message = "Permission denied."

        def has_permission(self, user, tool, **kwargs):
            view = viewset_class()
            view.action = getattr(tool, "drf_action", None)
            return drf_perm_class().has_permission(_FakeRequest(user, method), view)

    return _Adapter()


def _method_for(action):
    return {
        "list": "GET", "retrieve": "GET", "create": "POST",
        "update": "PUT", "partial_update": "PATCH", "destroy": "DELETE",
    }.get(action, "GET")


def _available_actions(viewset_class):
    actions = [a for a in STANDARD_ACTIONS if callable(getattr(viewset_class, a, None))]
    # Custom @action methods carry a `.mapping` attribute (DRF detail/list routes).
    for name in dir(viewset_class):
        attr = getattr(viewset_class, name, None)
        if callable(attr) and hasattr(attr, "mapping") and name not in actions:
            actions.append(name)
    return actions


def build_action_tool(
    *, name, action, serializer_class, model=None, queryset=None,
    permission_classes=None, description=None,
):
    """Create + register a ``Tool`` subclass for one viewset/model action."""

    def get_object(pk):
        qs = queryset if queryset is not None else model._default_manager.all()
        try:
            return qs.get(pk=pk)
        except Exception:
            raise NotFound(f"Not found: pk={pk}")

    def serialize(instance, many=False):
        return serializer_class(instance, many=many).data

    if action == "list":
        def run(self, user):
            qs = queryset if queryset is not None else model._default_manager.all()
            return list(serialize(qs, many=True))
    elif action == "retrieve":
        def run(self, user, pk):
            return serialize(get_object(pk))
    elif action == "destroy":
        def run(self, user, pk):
            obj = get_object(pk)
            obj.delete()
            return {"deleted": pk}
    elif action in ("create", "update", "partial_update"):
        partial = action == "partial_update"

        def run(self, user, **data):
            pk = data.pop("pk", None)
            if action == "create":
                serializer = serializer_class(data=data)
            else:
                serializer = serializer_class(get_object(pk), data=data, partial=partial)
            if not serializer.is_valid():
                raise Invalid("Validation failed.", errors=serializer.errors)
            instance = serializer.save()
            return serializer_class(instance).data
    else:  # custom @action -- best-effort: not supported for execution in v1
        def run(self, user, **kwargs):
            raise PermissionDenied(f"Custom action {action!r} is not executable via MCP yet.")

    # Input schema + validation strategy per action.
    def get_input_schema(self):
        if action in ("retrieve", "destroy"):
            return {"type": "object", "properties": {"pk": {"type": "integer"}}, "required": ["pk"]}
        if action in ("create", "update", "partial_update"):
            schema = serializer_schema(serializer_class, all_optional=(action == "partial_update"))
            if action in ("update", "partial_update"):
                schema["properties"]["pk"] = {"type": "integer"}
                schema["required"] = list(set(schema.get("required", []) + ["pk"]))
            return schema
        return {"type": "object", "properties": {}}

    def validate(self, arguments):
        # DRF serializer does field validation inside run(); just shape the kwargs.
        return dict(arguments or {})

    attrs = {
        "name": name,
        "description": description or f"{action} via {serializer_class.__name__}",
        "permission_classes": list(permission_classes or []),
        "drf_action": action,
        "run": run,
        "get_input_schema": get_input_schema,
        "validate": validate,
        "input_model": lambda self: None,
    }
    return type(f"{name.title().replace('_', '')}Tool", (Tool,), attrs)


def register_drf_viewset(viewset, prefix=None, actions=None):
    """Adapt a DRF ViewSet's actions into tools.

    ``prefix`` names the tools (``{prefix}_{action}``); defaults to the model/viewset
    name. ``actions`` restricts the set; otherwise mirrors what the viewset exposes.
    Returns the list of registered tool classes.
    """
    viewset_class = viewset if isinstance(viewset, type) else type(viewset)
    serializer_class = getattr(viewset_class, "serializer_class", None)
    model = None
    queryset = getattr(viewset_class, "queryset", None)
    if queryset is not None:
        model = queryset.model
    if serializer_class is None:
        raise ValueError(
            f"{viewset_class.__name__} has no serializer_class; pass a ViewSet that "
            "defines one (or use ModelToolset)."
        )

    if prefix is None:
        base = model.__name__.lower() if model is not None else viewset_class.__name__.lower()
        prefix = base

    available = _available_actions(viewset_class)
    chosen = [a for a in (actions or available) if a in available]

    drf_perms = list(getattr(viewset_class, "permission_classes", []) or [])

    registered = []
    for action in chosen:
        method = _method_for(action)
        perms = [_adapt_permission(p, viewset_class, method) for p in drf_perms]
        tool_cls = build_action_tool(
            name=f"{prefix}_{action}",
            action=action,
            serializer_class=serializer_class,
            model=model,
            queryset=queryset,
            permission_classes=perms,
        )
        registered.append(tool_cls)
    return registered
