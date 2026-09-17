import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEY_PARTS = ("token", "credential", "password", "secret", "private_key")
PERSONAL_TEXT_KEYS = {
    "comment",
    "exception",
    "full_name",
    "message_text",
    "reason",
    "student_name",
    "text",
    "username",
}


def sanitize_event(event: Mapping[str, Any], *, pseudonym_key: bytes) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in event.items():
        normalized = key.lower()
        if _is_external_user_id(normalized):
            sanitized[_reference_key(key)] = pseudonymize(value, key=pseudonym_key)
        elif normalized in PERSONAL_TEXT_KEYS or any(part in normalized for part in SENSITIVE_KEY_PARTS):
            sanitized[key] = "[redacted]"
        elif isinstance(value, Mapping):
            sanitized[key] = sanitize_event(value, pseudonym_key=pseudonym_key)
        else:
            sanitized[key] = value
    return sanitized


def pseudonymize(value: object, *, key: bytes) -> str | None:
    if value is None:
        return None
    digest = hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def _is_external_user_id(key: str) -> bool:
    return "external_user_id" in key or key in {
        "recipient_id",
        "telegram_user_id",
        "vk_user_id",
    }


def _reference_key(key: str) -> str:
    if "external_user_id" in key:
        return key.replace("external_user_id", "external_user_ref")
    if key == "recipient_id":
        return "recipient_ref"
    return "user_ref"
