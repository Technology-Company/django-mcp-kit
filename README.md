# django-mcp-kit

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
pip install django-mcp-kit   # everything: MCP SDK wire transport, OAuth, DRF on-ramp, singleserver
```

> Batteries included — no extras to remember. The MCP SDK + `uvicorn` (the only wire
> transport today), django-oauth-toolkit (OAuth resource server), DRF (the ViewSet/model
> on-ramp), and `singleserver` are all core dependencies. Their imports stay
> lazy/contained, so the architectural boundary holds in code even though the packages
> ship by default.

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

Deployment topologies: co-located ASGI (`django_mcp_kit.asgi.mount`),
singleserver-managed aux (`django_mcp_kit.services.connect` from gunicorn `post_fork`),
or a separate **systemd** unit (recommended for production SSE — samples in [`deploy/`](./deploy)).

## Develop

```bash
poetry install
poetry run pytest
```
