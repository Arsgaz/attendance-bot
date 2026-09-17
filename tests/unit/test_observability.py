from structlog.contextvars import get_contextvars

from observability.context import background_operation, client_operation
from observability.privacy import sanitize_event


def test_sensitive_fields_are_redacted_and_external_ids_are_pseudonymized() -> None:
    result = sanitize_event(
        {
            "event": "client.update.received",
            "external_user_id": "12345",
            "recipient_id": "12345",
            "username": "private-user",
            "bot_token": "secret-token",
            "nested": {"reason": "private reason"},
        },
        pseudonym_key=b"test-key",
    )

    assert result["event"] == "client.update.received"
    assert result["external_user_ref"] == result["recipient_ref"]
    assert result["external_user_ref"] != "12345"
    assert result["username"] == "[redacted]"
    assert result["bot_token"] == "[redacted]"
    assert result["nested"] == {"reason": "[redacted]"}


def test_client_operation_binds_and_restores_context() -> None:
    assert "correlation_id" not in get_contextvars()


def test_background_operation_binds_correlation_context() -> None:
    with background_operation(operation="sheet_sync.iteration") as operation:
        context = get_contextvars()
        assert context["correlation_id"] == operation.correlation_id
        assert context["operation"] == "sheet_sync.iteration"

    assert "correlation_id" not in get_contextvars()

    with client_operation(
        provider="telegram",
        external_user_id="12345",
        external_update_id="777",
        operation="client.update",
    ) as operation:
        context = get_contextvars()
        assert context["correlation_id"] == operation.correlation_id
        assert context["provider"] == "telegram"
        assert context["external_user_id"] == "12345"
        assert context["external_update_id"] == "777"
        assert operation.duration_ms >= 0

    assert "correlation_id" not in get_contextvars()
