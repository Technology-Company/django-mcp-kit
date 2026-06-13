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


def test_admin_panels_expose_all_fields():
    # All connector fields must be present in the admin form, in order. Regression:
    # editable=False once hid client_id entirely, so the generated Client ID never showed.
    panel_fields = [getattr(p, "field_name", None) for p in MCPConnectorSettings.panels]
    assert panel_fields == ["enabled", "app_name", "redirect_uris", "skip_consent", "client_id"]

    panels = {p.field_name: p for p in MCPConnectorSettings.panels}
    # Every field renders (editable) so it isn't dropped from the form...
    for name in panel_fields:
        assert MCPConnectorSettings._meta.get_field(name).editable is True
    # ...but the generated client_id is read-only (display only), the rest are editable.
    assert panels["client_id"].read_only is True
    for name in ["enabled", "app_name", "redirect_uris", "skip_consent"]:
        assert getattr(panels[name], "read_only", False) is False


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
