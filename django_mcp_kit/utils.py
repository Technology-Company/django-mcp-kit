"""Small shared helpers."""

from __future__ import annotations

from importlib import import_module


def import_object(path):
    """Import an object from a dotted path, tolerating attributes of classes.

    Supports an explicit ``"module.path:obj.attr"`` colon form, and a plain
    ``"module.path.obj.attr"`` form resolved by trying progressively shorter module
    prefixes (so ``"app.models.UserProfile.user_for_token"`` resolves the classmethod).
    """
    if ":" in path:
        module_path, attr_path = path.split(":", 1)
        obj = import_module(module_path)
        for name in attr_path.split("."):
            obj = getattr(obj, name)
        return obj

    parts = path.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for name in parts[i:]:
            obj = getattr(obj, name)
        return obj
    raise ImportError(f"Could not import {path!r}")
