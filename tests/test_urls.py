"""The Django discovery + health views (co-located / mounted topology)."""


def test_healthz_view(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_oauth_protected_resource_view(client):
    r = client.get("/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == "https://example.test/mcp"
    assert body["authorization_servers"] == ["https://example.test"]


def test_healthz_rejects_post(client):
    r = client.post("/healthz")
    assert r.status_code == 405
