"""The OAuth-client provisioning helper + management command."""

import pytest

from django_mcp_kit.oauth_client import DEFAULT_APP_NAME, ensure_oauth_application


@pytest.mark.django_db
def test_ensure_creates_public_pkce_client():
    from oauth2_provider.models import Application

    app, created = ensure_oauth_application("https://claude.ai/cb")
    assert created is True
    assert app.name == DEFAULT_APP_NAME
    assert app.client_type == Application.CLIENT_PUBLIC
    assert app.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE
    assert app.redirect_uris == "https://claude.ai/cb"
    assert app.skip_authorization is False
    assert app.client_id


@pytest.mark.django_db
def test_ensure_is_idempotent_and_updates():
    app1, created1 = ensure_oauth_application("https://a/cb", name="X")
    app2, created2 = ensure_oauth_application("https://b/cb", name="X", skip_authorization=True)
    assert created1 is True and created2 is False
    assert app1.pk == app2.pk
    app2.refresh_from_db()
    assert app2.redirect_uris == "https://b/cb"
    assert app2.skip_authorization is True


@pytest.mark.django_db
def test_command_creates_client_and_prints_id(capsys):
    from django.core.management import call_command

    call_command("create_mcp_oauth_client", "https://claude.ai/cb", "--name", "Cmd")
    out = capsys.readouterr().out
    assert "Created OAuth client 'Cmd'" in out
    assert "Client ID:" in out
    assert "Public client (PKCE)" in out

    from oauth2_provider.models import Application
    assert Application.objects.filter(name="Cmd").exists()


@pytest.mark.django_db
def test_command_skip_consent(capsys):
    from django.core.management import call_command
    from oauth2_provider.models import Application

    call_command("create_mcp_oauth_client", "https://a/cb", "--name", "C2", "--skip-consent")
    assert Application.objects.get(name="C2").skip_authorization is True
    assert "auto-approved" in capsys.readouterr().out
