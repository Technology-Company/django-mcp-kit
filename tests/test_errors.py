"""The MCPError taxonomy + service-error adapter."""

from django_mcp_kit.errors import Invalid, MCPError, from_service_error


def test_from_service_error_duck_typed():
    class ServiceError(Exception):
        detail = "boom"
        status = 404
        extra = {"k": 1}

    mapped = from_service_error(ServiceError())
    assert isinstance(mapped, MCPError)
    assert mapped.status == 404
    assert mapped.extra == {"k": 1}


def test_from_service_error_passthrough():
    err = MCPError("x")
    assert from_service_error(err) is err


def test_from_service_error_plain_exception():
    mapped = from_service_error(ValueError("nope"))
    assert isinstance(mapped, MCPError)
    assert mapped.detail == "nope"


def test_invalid_carries_errors_in_extra():
    err = Invalid("bad", errors={"name": ["required"]})
    assert err.extra["errors"] == {"name": ["required"]}


def test_message_includes_extra():
    err = MCPError("denied", extra={"limit": 30})
    assert "denied" in err.message
    assert "limit" in err.message


def test_message_without_extra():
    assert MCPError("plain").message == "plain"
