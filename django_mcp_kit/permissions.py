"""DRF-style permission classes.

A tool declares ``permission_classes = [...]`` and the dispatcher checks each one
*before* ``run()``. Object-level checks (Wagtail ``permissions_for_user``) stay
inside ``run()`` / the service function -- native authz, end to end.
"""

from __future__ import annotations


class BasePermission:
    """Subclass and implement :meth:`has_permission`.

    ``user``    the resolved, authenticated Django user (or ``None``).
    ``tool``    the ``Tool`` instance being invoked.
    ``kwargs``  the validated tool inputs.
    """

    message = "You do not have permission to use this tool."

    def has_permission(self, user, tool, **kwargs):  # pragma: no cover - interface
        raise NotImplementedError


class AllowAny(BasePermission):
    def has_permission(self, user, tool, **kwargs):
        return True


class IsAuthenticated(BasePermission):
    message = "Authentication is required."

    def has_permission(self, user, tool, **kwargs):
        return user is not None and getattr(user, "is_active", False)


class HasDjangoPerm(BasePermission):
    """Require a Django model permission, e.g. ``HasDjangoPerm("app.change_thing")``."""

    def __init__(self, perm):
        self.perm = perm
        self.message = f"Requires permission: {perm}"

    def has_permission(self, user, tool, **kwargs):
        return user is not None and user.has_perm(self.perm)
