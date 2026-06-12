"""Tools/resources for the dummy app -- exercised by the test suite and discovered
on app load via autodiscovery."""

from django.conf import settings

from django_mcp_kit import (
    BasePermission,
    Image,
    RateLimitedMixin,
    Schema,
    Tool,
    resource,
    tool,
)


class Echo(Tool):
    name = "echo"
    description = "Echo a message back."

    class Input(Schema):
        message: str

    def run(self, user, message):
        return {"echo": message}


class DenyAll(BasePermission):
    message = "Nope."

    def has_permission(self, user, tool, **kwargs):
        return False


class Secret(Tool):
    name = "secret"
    description = "Always denied."
    permission_classes = [DenyAll]

    class Input(Schema):
        pass

    def run(self, user):
        return {"ok": True}


class Snapshot(RateLimitedMixin, Tool):
    name = "snapshot"
    description = "Returns a tiny image (rich content)."

    class Input(Schema):
        pass

    def run(self, user):
        return Image(data="aGVsbG8=", format="png")


@tool(name="add", description="Add two numbers.")
def add(a: int, b: int = 0) -> dict:
    return {"sum": a + b}


@tool(name="whoami", description="Return the calling user's username.")
async def whoami(user) -> dict:
    return {"user": getattr(user, "username", None)}


class Publish(Tool):
    name = "publish"
    description = "Gated on a setting (the MCP_ALLOW_PUBLISH pattern)."

    def enabled():
        return getattr(settings, "MCP_ALLOW_PUBLISH", False)

    class Input(Schema):
        pass

    def run(self, user):
        return {"published": True}


@resource("greeting://hello")
def greeting(user) -> dict:
    return {"text": "hello"}


@resource("product://{pk}")
def product_resource(user, pk) -> dict:
    return {"pk": pk}
