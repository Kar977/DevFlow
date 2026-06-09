"""GitHub webhook signature verification and event payload parsing."""

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    payload: dict[str, Any]


def verify_signature(
    *, payload_bytes: bytes, secret: str, signature_header: str
) -> None:
    """Raise ValueError if the X-Hub-Signature-256 header doesn't match."""
    if not signature_header.startswith("sha256="):
        raise ValueError("Missing or invalid signature prefix (expected sha256=…).")
    expected_sig = (
        "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(expected_sig, signature_header):
        raise ValueError("Webhook signature mismatch — request rejected.")


def parse_event(event_type: str, payload: dict[str, Any]) -> WebhookEvent:
    return WebhookEvent(event_type=event_type, payload=payload)
