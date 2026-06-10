"""OAuth 2.1 resource server (django-oauth-toolkit).

Validate a DOT access token, resolve the Django user, and check required scopes. Also provides the RFC 9728
protected-resource metadata and the ``401 + WWW-Authenticate`` challenge -- these are
*ours*, not the SDK's.

``oauth2_provider`` is imported lazily, so it's only loaded when this backend is used.
"""

from __future__ import annotations

from .. import conf
from .base import Authenticator, bearer_token, resource_metadata_url


class OAuthResourceServer(Authenticator):
    def authenticate(self, request):
        token = bearer_token(request)
        if not token:
            return None

        from oauth2_provider.models import AccessToken as OAuthToken

        oauth_token = (
            OAuthToken.objects.filter(token=token).select_related("user").first()
        )
        if oauth_token is None or not oauth_token.is_valid():
            return None
        if oauth_token.user_id is None or not oauth_token.user.is_active:
            return None

        required = set(conf.get_setting("REQUIRED_SCOPES") or [])
        granted = set(oauth_token.scope.split() if oauth_token.scope else [])
        if required and not required <= granted:
            return None

        return oauth_token.user

    def challenge(self):
        meta = resource_metadata_url()
        return 401, {"WWW-Authenticate": f'Bearer resource_metadata="{meta}"'}


def protected_resource_metadata():
    """RFC 9728 metadata document served at /.well-known/oauth-protected-resource."""
    issuer = conf.get_setting("OAUTH_ISSUER_URL")
    resource = conf.get_setting("RESOURCE_SERVER_URL")
    return {
        "resource": resource,
        "authorization_servers": [issuer] if issuer else [],
        "scopes_supported": list(conf.get_setting("REQUIRED_SCOPES") or []),
        "bearer_methods_supported": ["header"],
    }
