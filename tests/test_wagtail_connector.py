"""The optional Wagtail settings page (django_mcp_kit.wagtail_connector).

Runs in the normal suite; Wagtail is a dev dependency (and the published `[wagtail]`
extra). The page provisions/updates the DOT OAuth client on save.
"""

import pytest

from oauth2_provider.models import Application

from django_mcp_kit.wagtail_connector.models import MCPConnectorSettings


@pytest.mark.django_db
def test_saving_enabled_settings_provisions_oauth_client():
    s = MCPConnectorSettings(
        enabled=True,
        app_name="My Wagtail Connector",
        redirect_uris="https://claude.ai/cb\nhttps://app/cb",
        skip_consent=True,
    )
    s.save()

    assert s.client_id
    app = Application.objects.get(client_id=s.client_id)
    assert app.name == "My Wagtail Connector"          # the name shown on the consent page
    assert app.skip_authorization is True
    assert app.redirect_uris == "https://claude.ai/cb https://app/cb"
    assert app.client_type == Application.CLIENT_PUBLIC


@pytest.mark.django_db
def test_disabled_settings_do_not_provision():
    MCPConnectorSettings(enabled=False, redirect_uris="https://x/cb").save()
    assert Application.objects.count() == 0


@pytest.mark.django_db
def test_rename_updates_same_client():
    s = MCPConnectorSettings(enabled=True, app_name="First", redirect_uris="https://x/cb")
    s.save()
    first_id = s.client_id

    s.app_name = "Renamed"
    s.save()
    assert s.client_id == first_id
    assert Application.objects.count() == 1
    assert Application.objects.get(client_id=first_id).name == "Renamed"
