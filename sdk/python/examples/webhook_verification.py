"""
Webhook signature verification example for the SoroScan SDK.

SoroScan signs every webhook delivery with Ed25519 and sends the signature in
the ``X-Signature`` header as ``ed25519=<base64-signature>``. Always verify the
raw request body before parsing or trusting a delivery.

This example contains a self-contained signed payload you can run immediately,
followed by the pattern for a real webhook handler.
"""

import json
import os

from soroscan import verify_webhook_signature

# Demo payload and signature generated with a throwaway Ed25519 key pair.
DEMO_PAYLOAD = (
    b'{"event_type":"transfer","contract_id":"CCAAA...",'
    b'"ledger":123456,"payload":{"amount":"100"}}'
)
DEMO_SIGNATURE_HEADER = (
    "ed25519=D7kHZlAypN/+fRF1M7oLX/xFRlABPPuOkBAS68WuFJVuxBR2t0NbGZCZLxzWW922"
    "CPAtkg8yKNG04Y8N41a7Bw=="
)
DEMO_PUBLIC_KEY_B64 = "Y5EIIkIHNKJz2H/sFjqrBmylusCCukQsoE4JYkKF8Bc="


def verify_signed_delivery() -> None:
    """Verify a known-good delivery and reject a tampered payload."""
    is_valid = verify_webhook_signature(
        payload=DEMO_PAYLOAD,
        signature_header=DEMO_SIGNATURE_HEADER,
        public_key_b64=DEMO_PUBLIC_KEY_B64,
    )
    print(f"Signed payload verified: {is_valid}")

    tampered_payload = DEMO_PAYLOAD.replace(b'"amount":"100"', b'"amount":"999"')
    tampered_is_valid = verify_webhook_signature(
        payload=tampered_payload,
        signature_header=DEMO_SIGNATURE_HEADER,
        public_key_b64=DEMO_PUBLIC_KEY_B64,
    )
    print(f"Tampered payload verified: {tampered_is_valid}")

    assert is_valid, "the demo signature should verify"
    assert not tampered_is_valid, "tampered payloads must be rejected"

    event = json.loads(DEMO_PAYLOAD)
    print(f"Event type: {event['event_type']}, ledger: {event['ledger']}")


def handle_webhook(request) -> tuple[str, int]:
    """
    Example handler for Flask/FastAPI-style request objects.

    ``request.body`` must return the raw bytes exactly as received. Do not
    re-serialize the parsed JSON before verifying, because whitespace and key
    ordering changes will invalidate the signature.
    """
    raw_body = request.body
    signature_header = request.headers.get("X-Signature", "")
    public_key_b64 = os.environ["SOROSCAN_WEBHOOK_PUBLIC_KEY"]

    if not verify_webhook_signature(raw_body, signature_header, public_key_b64):
        return "invalid signature", 401

    event = json.loads(raw_body)
    return f"accepted {event['event_type']}", 200


if __name__ == "__main__":
    verify_signed_delivery()
