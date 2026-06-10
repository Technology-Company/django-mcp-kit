import pytest

from django_mcp_kit.auth import (
    OAuthResourceServer,
    StaticBearer,
    authenticate_request,
    protected_resource_metadata,
)
from django_mcp_kit.auth.base import bearer_token


class Req:
    """Header-mapping request shim."""

    def __init__(self, authorization=None):
        self.headers = {}
        if authorization is not None:
            self.headers["Authorization"] = authorization


def test_bearer_token_extraction():
    assert bearer_token(Req("Bearer abc123")) == "abc123"
    assert bearer_token(Req("Basic xxx")) is None
    assert bearer_token(Req()) is None


def test_static_bearer_valid():
    user = StaticBearer().authenticate(Req("Bearer good-token"))
    assert user is not None and user.username == "bob"


def test_static_bearer_invalid():
    assert StaticBearer().authenticate(Req("Bearer wrong")) is None
    assert StaticBearer().authenticate(Req()) is None


def test_authenticate_request_success():
    user, challenge = authenticate_request(Req("Bearer good-token"), backends=[StaticBearer()])
    assert user is not None
    assert challenge is None


def test_authenticate_request_challenge():
    user, challenge = authenticate_request(Req(), backends=[OAuthResourceServer()])
    assert user is None
    status, headers = challenge
    assert status == 401
    assert "resource_metadata=" in headers["WWW-Authenticate"]
    assert "/.well-known/oauth-protected-resource" in headers["WWW-Authenticate"]


def test_protected_resource_metadata_shape():
    meta = protected_resource_metadata()
    assert meta["resource"] == "https://example.test/mcp"
    assert meta["authorization_servers"] == ["https://example.test"]
    assert "mcp" in meta["scopes_supported"]
    assert meta["bearer_methods_supported"] == ["header"]


@pytest.mark.django_db
def test_oauth_resource_server_token():
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from oauth2_provider.models import AccessToken, Application

    User = get_user_model()
    user = User.objects.create(username="alice", is_active=True)
    app = Application.objects.create(
        name="t",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://example.test/cb",
        user=user,
    )
    AccessToken.objects.create(
        user=user, token="valid-oauth", application=app, scope="mcp",
        expires=timezone.now() + timedelta(hours=1),
    )

    rs = OAuthResourceServer()

    class Req2:
        def __init__(self, tok):
            self.headers = {"Authorization": f"Bearer {tok}"}

    assert rs.authenticate(Req2("valid-oauth")).pk == user.pk
    assert rs.authenticate(Req2("nope")) is None


@pytest.mark.django_db
def test_backend_chain_falls_through_oauth_to_static():
    # OAuth backend returns None for a non-OAuth token, StaticBearer then resolves it.
    user, challenge = authenticate_request(
        Req("Bearer good-token"), backends=[OAuthResourceServer(), StaticBearer()])
    assert challenge is None
    assert user is not None and user.username == "bob"


@pytest.mark.django_db
def test_oauth_expired_token_rejected():
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from oauth2_provider.models import AccessToken, Application

    User = get_user_model()
    user = User.objects.create(username="dave", is_active=True)
    app = Application.objects.create(
        name="t3", client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://example.test/cb", user=user)
    AccessToken.objects.create(
        user=user, token="expired", application=app, scope="mcp",
        expires=timezone.now() - timedelta(hours=1))  # already expired

    class Req2:
        headers = {"Authorization": "Bearer expired"}

    assert OAuthResourceServer().authenticate(Req2()) is None


@pytest.mark.django_db
def test_oauth_required_scope_enforced(settings):
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from oauth2_provider.models import AccessToken, Application

    User = get_user_model()
    user = User.objects.create(username="carol", is_active=True)
    app = Application.objects.create(
        name="t2",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://example.test/cb",
        user=user,
    )
    AccessToken.objects.create(
        user=user, token="wrong-scope", application=app, scope="read",
        expires=timezone.now() + timedelta(hours=1),
    )

    class Req2:
        headers = {"Authorization": "Bearer wrong-scope"}

    # REQUIRED_SCOPES=["mcp"] but token only has "read" -> rejected.
    assert OAuthResourceServer().authenticate(Req2()) is None
