"""Run the MCP ASGI app with uvicorn.

Standard ``--host/--port/--socket`` args so the singleserver ``command`` template and
the systemd unit are interchangeable. ``--timeout-graceful-shutdown`` bounds drain time
so long-lived SSE streams don't stall stop/restart under singleserver/systemd.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ... import conf


class Command(BaseCommand):
    help = "Run the django-mcp-kit MCP server (ASGI) with uvicorn."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=conf.get_setting("PORT", 8810))
        parser.add_argument("--socket", default=None, help="Unix socket path (overrides host/port).")
        parser.add_argument("--reload", action="store_true")
        parser.add_argument("--timeout-graceful-shutdown", type=int, default=15)
        parser.add_argument("--log-level", default="info")

    def handle(self, *args, **options):
        import uvicorn

        from ...asgi import get_application

        kwargs = {
            "log_level": options["log_level"],
            "timeout_graceful_shutdown": options["timeout_graceful_shutdown"],
        }
        if options["socket"]:
            kwargs["uds"] = options["socket"]
            target = f"unix socket {options['socket']}"
        else:
            kwargs["host"] = options["host"]
            kwargs["port"] = options["port"]
            target = f"{options['host']}:{options['port']}"

        if options["reload"]:
            # Reload needs an import string; rely on DJANGO_SETTINGS_MODULE in env.
            self.stdout.write(self.style.NOTICE(f"Starting MCP server (reload) on {target}"))
            uvicorn.run("django_mcp_kit.asgi:get_application", factory=True, reload=True, **kwargs)
        else:
            self.stdout.write(self.style.NOTICE(f"Starting MCP server on {target}"))
            uvicorn.run(get_application(), **kwargs)
