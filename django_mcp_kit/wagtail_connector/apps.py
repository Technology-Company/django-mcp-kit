from django.apps import AppConfig


class MCPWagtailConnectorConfig(AppConfig):
    name = "django_mcp_kit.wagtail_connector"
    label = "mcp_wagtail_connector"
    verbose_name = "MCP connector (Wagtail)"
    default_auto_field = "django.db.models.BigAutoField"
