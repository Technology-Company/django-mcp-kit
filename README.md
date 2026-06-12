# django-mcp-kit

[![PyPI version](https://img.shields.io/pypi/v/django-mcp-kit.svg)](https://pypi.org/project/django-mcp-kit/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-mcp-kit.svg)](https://pypi.org/project/django-mcp-kit/)
[![Django](https://img.shields.io/badge/Django-4.2%2B-092e20.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Turns Django/Wagtail code into MCP tools (and resources) for Claude clients — without
coupling your business logic to any MCP framework.

- **Transport-neutral core.** A registry + dispatcher own `initialize` / `tools.list` /
  `tools.call`; the official MCP SDK is used **only at the wire** (`transports/sdk.py`)
  and is swappable. No FastMCP.
- **Native Django authz.** DRF-style `permission_classes` checked before `run()`; object
  permissions (Wagtail `permissions_for_user`) stay in your service layer.
- **Pluggable auth.** Static bearer tokens *and* OAuth 2.1 resource server
  (django-oauth-toolkit) behind one `Authenticator` interface, with RFC 9728 discovery
  metadata and the `401 + WWW-Authenticate` handshake.
- **On-ramps.** Register a DRF `ViewSet`, expose a model (read-only by default), or
  declare MCP resources.

## Install

```bash
pip install django-mcp-kit              # core: MCP SDK wire transport, OAuth, DRF on-ramp, singleserver
pip install "django-mcp-kit[wagtail]"   # + the optional Wagtail admin settings page
```

> Batteries included. The MCP SDK + `uvicorn` (the only wire transport today),
> django-oauth-toolkit (OAuth resource server), DRF (the ViewSet/model on-ramp), and
> `singleserver` are all core dependencies — their imports stay lazy/contained, so the
> architectural boundary holds in code even though the packages ship by default. The one
> optional extra is **`[wagtail]`**, for the Wagtail admin settings page (Django-only
> projects don't need Wagtail).

## Quickstart

```python
# settings.py
INSTALLED_APPS += ["django_mcp_kit"]
DJANGO_MCP_KIT = {
    "SERVER_NAME": "my-content",
    "AUTH_BACKENDS": [
        "django_mcp_kit.auth.OAuthResourceServer",
        "django_mcp_kit.auth.StaticBearer",
    ],
    "STATIC_BEARER_RESOLVER": "myapp.models:UserProfile.user_for_token",
    "OAUTH_ISSUER_URL": "https://example.com",
    "RESOURCE_SERVER_URL": "https://example.com/mcp",
    "REQUIRED_SCOPES": ["mcp"],
}

# urls.py — discovery + health for the Django site
path("", include("django_mcp_kit.urls")),  # /healthz, /.well-known/oauth-protected-resource
```

```python
# myapp/mcp_tools.py — autodiscovered on app load
from django_mcp_kit import Tool, Schema, tool
from . import services

class PatchBlock(Tool):
    name = "patch_block"
    description = "Replace one homepage block by id; saves a DRAFT."

    class Input(Schema):
        block_id: str
        value: dict

    def run(self, user, block_id, value):           # sync — runs off the event loop
        return services.save_homepage_draft(user, block_id=block_id, value=value)

@tool(name="get_draft", description="Latest homepage draft.")
def get_draft(user) -> dict:
    return services.homepage_draft()
```

```python
# Register a DRF ViewSet (one tool per action) or a model (read-only by default)
from django_mcp_kit.drf import register_drf_viewset
from django_mcp_kit.models import ModelToolset

register_drf_viewset(OrderViewSet, prefix="order")  # order_list, order_create, …

class ProductToolset(ModelToolset):
    model = Product
    actions = ["list", "retrieve"]   # add "create"/"update"/"delete" to opt in
    as_resource = True
```

## Run it

```bash
python manage.py runserver_mcp --port 8810      # ASGI/uvicorn MCP process
```

## Deployment

The MCP endpoint is **always ASGI** (Streamable HTTP uses SSE), but how it runs is a
choice. All topologies run the same code — `runserver_mcp` serving the app from
`django_mcp_kit.asgi:get_application` — only the process management differs. Pick by how
your *site* is served and how much isolation you want:

| Topology | Site stays WSGI | Process | Best for |
|---|:--:|---|---|
| **A — Co-located** | no (site → ASGI) | one ASGI process | single-service / already-ASGI sites |
| **B — singleserver aux** | yes | gunicorn boots the MCP process, workers share it | dev == prod, no systemd |
| **C — separate systemd unit** | yes | independent ASGI daemon | production SSE (recommended) |

Health checks point at **`/healthz`** (a plain 200) — never `/mcp`, which is the
Streamable-HTTP endpoint and returns 4xx to a bare GET.

### A — Co-located (one ASGI process)

Mount the MCP app beside your Django ASGI app; requests to `/mcp` (and `/healthz`,
`/.well-known/...`) go to MCP, everything else to Django:

```python
# asgi.py
from django.core.asgi import get_asgi_application
from django_mcp_kit.asgi import mount

application = mount(get_asgi_application())   # serves /mcp on the same process
```

### B — singleserver-managed aux ([`deploy/gunicorn.conf.py`](./deploy/gunicorn.conf.py))

Your site stays WSGI/gunicorn. The first gunicorn worker boots the MCP process; all
workers share it via an atomic socket lock (no systemd). Wire it in `post_fork`:

```python
# gunicorn.conf.py
def post_fork(server, worker):
    from django_mcp_kit.services import connect
    connect()
```

Point your front-end proxy `/mcp` at `DJANGO_MCP_KIT["PORT"]` (default `8810`). The
shipped `SingleServer` uses `health_check_url="/healthz"` and a bounded graceful shutdown.

### C — Separate systemd unit ([`deploy/django-mcp.service`](./deploy/django-mcp.service))

Run the MCP server as its own daemon — decoupled lifecycle, real graceful restart. The
sample unit runs `runserver_mcp` with a bounded `--timeout-graceful-shutdown` (so
long-lived SSE streams don't stall stop/restart) and `Restart=always`. Edit the paths/user,
then:

```bash
sudo cp deploy/django-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now django-mcp
```

### nginx ([`deploy/nginx-mcp.conf`](./deploy/nginx-mcp.conf))

For B and C, proxy `/mcp` to the MCP process. SSE requires **buffering off** and long read
timeouts — the sample sets `proxy_buffering off` and `proxy_read_timeout 3600s`, and also
proxies the `/.well-known/oauth-protected-resource` metadata. Add it inside your `server {}`
block and reload nginx.

## Authorization Server (OAuth) setup

This library is the **Resource Server** — it validates bearer tokens and serves the
RFC 9728 discovery metadata. It does **not** provide the **Authorization Server** (the
login, `/o/authorize`, `/o/token`, and the **consent page**). That role is
django-oauth-toolkit (DOT), which ships as a dependency but must be wired up by the
project:

```python
# settings.py
INSTALLED_APPS += ["oauth2_provider"]
OAUTH2_PROVIDER = {
    "SCOPES": {"mcp": "Access MCP tools"},
    "PKCE_REQUIRED": True,   # public clients (browser/native, e.g. claude.ai)
}

# urls.py — mount the Authorization Server endpoints
path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
```

### Provisioning the OAuth client

Register an OAuth client (a DOT `Application`) per connector with the bundled command —
idempotent, public + PKCE by default:

```bash
python manage.py create_mcp_oauth_client https://claude.ai/api/mcp/auth_callback \
    --name "My connector"        # name shown on the consent page; --skip-consent to auto-approve
```

The client name defaults to `DJANGO_MCP_KIT["OAUTH_APP_NAME"]` (`"MCP connector"`) when
`--name` is omitted. The command prints the **Client ID** to paste into the connector.
`django_mcp_kit.oauth_client.ensure_oauth_application(...)` is the same helper if you'd
rather provision from code.

### The consent page

The consent screen is rendered by **DOT's `AuthorizationView`** at `/o/authorize/` using
its default template **`oauth2_provider/authorize.html`** (a plain approve/deny form).
Whether it appears is controlled per-client by **`Application.skip_authorization`**:

- `skip_authorization=False` (DOT default) — the user is shown the consent page on first
  authorization.
- `skip_authorization=True` — consent is auto-approved (no page). Reasonable for a
  trusted first-party connector.

The name shown on that consent page is the `Application.name` — set it per client with
`create_mcp_oauth_client --name`, or change the default via `DJANGO_MCP_KIT["OAUTH_APP_NAME"]`.
To customise the consent UI, override `oauth2_provider/authorize.html` in your own
templates directory. This library has no opinion on and no default for the consent page —
it only consumes the access token DOT issues.

### Configuring it from the Wagtail admin (optional)

For Wagtail projects, add the optional app to get a **"MCP connector"** page under the
admin **Settings** menu that provisions/updates the client on save:

```bash
pip install "django-mcp-kit[wagtail]"    # Wagtail 6.x or 7.x
```
```python
INSTALLED_APPS += ["django_mcp_kit.wagtail_connector"]
# then: python manage.py migrate
```

Fields: enable, the consent-page name, redirect URIs, and skip-consent. **Access is
gated by the `change_mcpconnectorsettings` permission — i.e. superusers only by default**;
delegate to specific staff by granting that permission via a Group. Wagtail is *not* a
core dependency — it's the optional `[wagtail]` extra, so Django-only projects skip it.

## Develop

```bash
poetry install
poetry run pytest
```
