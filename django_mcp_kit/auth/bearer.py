"""Static bearer-token authentication.

Resolves a token to a user via a project-supplied callable, configured as a dotted
path in ``DJANGO_MCP_KIT["STATIC_BEARER_RESOLVER"]`` (e.g.
``"myapp.models:UserProfile.user_for_token"``). Keeps the per-user token model that
Claude Code / Desktop use today.
"""

from __future__ import annotations

from .. import conf
from ..utils import import_object
from .base import Authenticator, bearer_token


class StaticBearer(Authenticator):
    def __init__(self):
        self._resolver = None

    def resolver(self):
        if self._resolver is None:
            path = conf.get_setting("STATIC_BEARER_RESOLVER")
            self._resolver = import_object(path) if path else False
        return self._resolver or None

    def authenticate(self, request):
        token = bearer_token(request)
        if not token:
            return None
        resolve = self.resolver()
        if resolve is None:
            return None
        user = resolve(token)
        if user is None or not getattr(user, "is_active", False):
            return None
        return user
