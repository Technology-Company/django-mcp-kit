"""Optional Wagtail admin settings page for configuring the MCP OAuth client.

This is an **optional** app (it requires Wagtail). Add
``"django_mcp_kit.wagtail_connector"`` to ``INSTALLED_APPS`` to get a "MCP connector"
settings page in the Wagtail admin. Saving it (when enabled) provisions/updates the DOT
``Application`` via :func:`django_mcp_kit.oauth_client.ensure_oauth_application` -- the
same helper the ``create_mcp_oauth_client`` command uses.

Supported on Wagtail 6.x and 7.x.
"""

from __future__ import annotations

from django.db import models
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from .. import conf
from ..oauth_client import ensure_oauth_application


@register_setting(icon="key")
class MCPConnectorSettings(BaseGenericSetting):
    enabled = models.BooleanField(
        default=False, help_text="Provision/update the OAuth client when this is saved.")
    app_name = models.CharField(
        max_length=150, blank=True,
        help_text="Client name shown on the OAuth consent page. "
                  "Blank uses DJANGO_MCP_KIT['OAUTH_APP_NAME'].")
    redirect_uris = models.TextField(
        blank=True, help_text="Allowed redirect URIs, one per line.")
    skip_consent = models.BooleanField(
        default=False, help_text="Auto-approve authorization (skip the consent page).")
    client_id = models.CharField(max_length=100, blank=True, editable=False)

    class Meta:
        verbose_name = "MCP connector"

    def save(self, *args, **kwargs):
        if self.enabled and self.redirect_uris.strip():
            app, _ = ensure_oauth_application(
                " ".join(self.redirect_uris.split()),
                name=self.app_name or conf.get_setting("OAUTH_APP_NAME"),
                skip_authorization=self.skip_consent,
                client_id=self.client_id or None,
            )
            self.client_id = app.client_id
        super().save(*args, **kwargs)
