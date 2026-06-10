# Sample gunicorn config for topology B (singleserver-managed MCP).
# The site stays WSGI; the first worker boots the MCP process, all workers share it.

bind = "127.0.0.1:8000"
workers = 3


def post_fork(server, worker):
    # Boots the MCP server once (atomic socket lock); other workers attach as clients.
    from django_mcp_kit.services import connect

    connect()
