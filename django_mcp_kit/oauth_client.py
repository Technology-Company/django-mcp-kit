"""Provision the OAuth client (a django-oauth-toolkit ``Application``) for an MCP
connector. Shared by the ``create_mcp_oauth_client`` command and the optional Wagtail
settings page.

``oauth2_provider`` is imported lazily so importing this module never requires it.
"""

from __future__ import annotations

from . import conf

# Fallback when no name is given and no OAUTH_APP_NAME setting is configured.
DEFAULT_APP_NAME = "MCP connector"


def ensure_oauth_application(
    redirect_uris,
    *,
    name=None,
    public=True,
    skip_authorization=False,
    client_id=None,
):
    """Create or update the connector's OAuth ``Application`` (idempotent).

    ``redirect_uris``      space-separated allowed redirect URIs.
    ``name``               the client name shown on the consent page; defaults to
                           ``DJANGO_MCP_KIT["OAUTH_APP_NAME"]``.
    ``public``             public client (PKCE, no secret) vs confidential.
    ``skip_authorization`` auto-approve (skip the consent page) vs prompt.
    ``client_id``          when given, locate the existing app by client_id so a
                           rename (changing ``name``) updates it instead of creating
                           a duplicate.

    Returns ``(application, created)``.
    """
    from oauth2_provider.models import Application

    if name is None:
        name = conf.get_setting("OAUTH_APP_NAME", DEFAULT_APP_NAME)

    fields = {
        "name": name,
        "client_type": Application.CLIENT_PUBLIC if public else Application.CLIENT_CONFIDENTIAL,
        "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
        "redirect_uris": redirect_uris,
        "skip_authorization": skip_authorization,
    }

    existing = Application.objects.filter(client_id=client_id).first() if client_id else None
    if existing is None:
        defaults = {k: v for k, v in fields.items() if k != "name"}
        app, created = Application.objects.get_or_create(name=name, defaults=defaults)
        if created:
            return app, True
    else:
        app = existing

    for key, value in fields.items():
        setattr(app, key, value)
    app.save()
    return app, False
