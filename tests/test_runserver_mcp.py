"""The runserver_mcp command wires uvicorn correctly (without actually serving)."""

import pytest

pytest.importorskip("mcp")


def test_runserver_mcp_invokes_uvicorn(monkeypatch):
    import uvicorn
    from django.core.management import call_command

    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(uvicorn, "run", fake_run)
    call_command("runserver_mcp", "--host", "127.0.0.1", "--port", "9999")

    assert callable(captured["app"])
    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 9999
    # Graceful-shutdown bound is always passed so SSE streams don't stall stop/restart.
    assert captured["kwargs"]["timeout_graceful_shutdown"] == 15


def test_runserver_mcp_socket_mode(monkeypatch):
    import uvicorn
    from django.core.management import call_command

    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(kw))
    call_command("runserver_mcp", "--socket", "/tmp/mcp.sock")

    assert captured["uds"] == "/tmp/mcp.sock"
    assert "host" not in captured and "port" not in captured
