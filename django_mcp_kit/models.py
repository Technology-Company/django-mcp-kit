"""Opt-in model exposure.

``ModelToolset`` generates tools straight from a Django model, consistent with the
class-based ``Tool`` idiom.

⚠️ Raw-model CRUD **bypasses the service layer** and Wagtail's draft/publish,
revisions, and ``permissions_for_user`` checks. It is for simple, non-Wagtail-workflow
models only. Default is **read-only**; writes are explicit, per-model opt-in. For
Wagtail content, write a ``Tool`` that delegates to a service function instead.
"""

from __future__ import annotations

from .drf import WRITE_ACTIONS, build_action_tool
from .resources import Resource


def _default_serializer(model, fields):
    from rest_framework import serializers

    meta = type("Meta", (), {"model": model, "fields": fields})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


def _looks_wagtail_managed(model):
    # Wagtail Page-workflow models expose save_revision/permissions_for_user.
    return hasattr(model, "save_revision") and hasattr(model, "permissions_for_user")


class ModelToolset:
    model = None
    actions = ["list", "retrieve"]  # read-only by default
    fields = "__all__"
    serializer_class = None
    permission_classes = []
    as_resource = False
    prefix = None
    allow_wagtail_writes = False
    abstract = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("abstract") or cls.model is None:
            return
        cls._build()

    @classmethod
    def _build(cls):
        write_requested = set(cls.actions) & WRITE_ACTIONS
        if write_requested and _looks_wagtail_managed(cls.model) and not cls.allow_wagtail_writes:
            raise ValueError(
                f"{cls.model.__name__} looks Wagtail-managed (has save_revision / "
                "permissions_for_user). Raw-model writes would bypass the draft/publish "
                "workflow and object permissions. Write a Tool delegating to a service "
                "function instead, or set allow_wagtail_writes=True to override."
            )

        serializer_class = cls.serializer_class or _default_serializer(cls.model, cls.fields)
        prefix = cls.prefix or cls.model.__name__.lower()

        for action in cls.actions:
            build_action_tool(
                name=f"{prefix}_{action}",
                action=action,
                serializer_class=serializer_class,
                model=cls.model,
                permission_classes=cls.permission_classes,
            )

        if cls.as_resource:
            cls._register_resource(prefix, serializer_class)

    @classmethod
    def _register_resource(cls, prefix, serializer_class):
        model = cls.model

        def read(self, user, pk):
            obj = model._default_manager.get(pk=pk)
            return serializer_class(obj).data

        attrs = {
            "uri": f"{prefix}://{{pk}}",
            "name": f"{prefix} resource",
            "description": f"A single {model.__name__} by primary key.",
            "mime_type": "application/json",
            "permission_classes": list(cls.permission_classes or []),
            "read": read,
        }
        # Building the subclass auto-registers it (Resource.__init_subclass__).
        type(f"{model.__name__}Resource", (Resource,), attrs)
