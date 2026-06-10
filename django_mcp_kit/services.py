"""SingleServer factory for the singleserver-managed topology (topology B).

The first gunicorn worker boots the MCP process; all workers share it via an atomic
socket lock -- no systemd unit. Other aux processes can sit alongside it.
``singleserver`` is imported lazily so it's only loaded when this topology is used.

IMPORTANT: the health check points at ``/healthz``, NOT ``/mcp`` -- a bare GET
to the Streamable-HTTP endpoint returns 4xx and would trigger a restart loop. Graceful
shutdown is bounded so long-lived SSE streams don't stall stop/restart.

Wiring (project side)::

    # gunicorn.conf.py
    def post_fork(server, worker):
        from django_mcp_kit.services import mcp_server
        mcp_server().connect()

For production SSE workloads, topology C (systemd ASGI) is the recommended default
(decoupled lifecycle, real graceful restart); see ``deploy/``.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from . import conf


@lru_cache(maxsize=1)
def mcp_server():
    """Return the process-wide :class:`singleserver.SingleServer` for the MCP app."""
    from singleserver import SingleServer

    port = conf.get_setting("PORT", 8810)
    return SingleServer(
        name=conf.get_setting("SERVER_NAME", "django-mcp-kit"),
        command=[
            "python", "manage.py", "runserver_mcp",
            "--host", "127.0.0.1", "--port", "{port}",
        ],
        port=port,
        health_check_url="/healthz",
        restart_on_failure=True,
        shutdown_timeout=15.0,
        cwd=str(getattr(settings, "BASE_DIR", ".")),
    )


def connect():
    """Convenience for gunicorn ``post_fork``: boot/attach the MCP process."""
    return mcp_server().connect()
