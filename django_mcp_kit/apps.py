from django.apps import AppConfig


class DjangoMCPKitConfig(AppConfig):
    name = "django_mcp_kit"
    verbose_name = "Django MCP Kit"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Import every app's mcp_tools.py so tools/resources self-register.
        from .registry import autodiscover

        autodiscover()
