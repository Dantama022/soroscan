"""Integration test: simulator delivered end-to-end against a verifying backend.

The backend independently verifies the HMAC (``X-SoroScan-Signature``) and Ed25519
(``X-Signature``) signatures using the same contract as the Django receiver
(``django-backend/soroscan/webhook_signing.py`` and
``ingest/tasks.py::_build_webhook_signature_header``), then returns the production
acknowledgement header only when both signatures are valid. This guards against the
simulator's signing/delivery behaviour drifting from the real webhook contract.

Collected by the Webhook Simulator CI workflow (``pytest``) alongside the unit tests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tests.conftest import header_value
from webhook_simulator.cli import main
from webhook_simulator.signing import ed25519_public_key_base64

SECRET = "integration-secret"
SEED_HEX = "11" * 32  # 32-byte Ed25519 private key seed (64 hex chars)
_HMAC_PREFIX = "sha256="
_ED25519_PREFIX = "ed25519="


def _verify_hmac(body: bytes, headers: dict[str, str], secret: str) -> bool:
    """Recompute the production HMAC-SHA256 and compare it (receiver side)."""
    sig = header_value(headers, "X-SoroScan-Signature")
    if not sig or not sig.startswith(_HMAC_PREFIX):
        return False
    expected = hmac.new(
        secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig, f"{_HMAC_PREFIX}{expected}")


def _verify_ed25519(body: bytes, headers: dict[str, str], public_key_b64: str) -> bool:
    """Verify the Ed25519 signature against the configured public key."""
    sig = header_value(headers, "X-Signature")
    if not sig or not sig.startswith(_ED25519_PREFIX):
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64)
        )
        public_key.verify(base64.b64decode(sig[len(_ED25519_PREFIX) :]), body)
        return True
    except (InvalidSignature, ValueError):
        return False


class VerifyingHandler(BaseHTTPRequestHandler):
    """Receiver that enforces signature verification before acknowledging."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length)
        headers = {k: v for k, v in self.headers.items()}
        secret = self.server.secret  # type: ignore[attr-defined]
        public_key_b64 = self.server.public_key_b64  # type: ignore[attr-defined]
        hmac_ok = _verify_hmac(body, headers, secret)
        ed25519_ok = _verify_ed25519(body, headers, public_key_b64)
        record = {
            "path": self.path,
            "headers": headers,
            "body": body,
            "hmac_valid": hmac_ok,
            "ed25519_valid": ed25519_ok,
            "timestamp": header_value(headers, "X-SoroScan-Timestamp"),
            "verified": hmac_ok and ed25519_ok,
        }
        self.server.requests.append(record)  # type: ignore[attr-defined]
        self._respond(200 if (hmac_ok and ed25519_ok) else 401)

    def _respond(self, status: int) -> None:
        body = b"ok" if status < 300 else b"no"
        self.send_response(status)
        if status < 300:
            self.send_header("X-SoroScan-Ack", "ok")
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def verifying_backend():
    server = ThreadingHTTPServer(("127.0.0.1", 0), VerifyingHandler)
    server.requests = []  # type: ignore[attr-defined]
    server.secret = SECRET  # type: ignore[attr-defined]
    server.public_key_b64 = ed25519_public_key_base64(SEED_HEX)  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    server.base_url = f"http://{host}:{port}/webhook"  # type: ignore[attr-defined]
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _run_simulator(
    url: str, *, secret: str = SECRET, ed25519_seed: str = SEED_HEX
) -> int:
    """Drive the simulator through its CLI against ``url`` (end-to-end)."""
    return main(
        [
            "--url",
            url,
            "--sample",
            "--secret",
            secret,
            "--ed25519-seed",
            ed25519_seed,
            "--require-ack",
            "--output",
            "json",
        ]
    )


def test_simulator_accepted_by_verifying_backend(verifying_backend, capsys):
    code = _run_simulator(verifying_backend.base_url)
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["success"] is True
    assert data["http_status"] == 200
    assert data["ack_status"] == "valid"

    assert len(verifying_backend.requests) == 1
    record = verifying_backend.requests[0]
    assert record["verified"] is True
    assert record["hmac_valid"] is True
    assert record["ed25519_valid"] is True
    assert record["timestamp"]

    # Independent contract re-check directly on the recorded request.
    body = record["body"]
    expected_hmac = hmac.new(
        SECRET.encode("utf-8"), msg=body, digestmod=hashlib.sha256
    ).hexdigest()
    assert header_value(record["headers"], "X-SoroScan-Signature") == (
        f"{_HMAC_PREFIX}{expected_hmac}"
    )
    public_key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(ed25519_public_key_base64(SEED_HEX))
    )
    ed25519_header = header_value(record["headers"], "X-Signature")
    public_key.verify(base64.b64decode(ed25519_header.split("=", 1)[1]), body)


def test_backend_rejects_wrong_hmac_secret(verifying_backend):
    code = _run_simulator(verifying_backend.base_url, secret="wrong-secret")
    assert code == 1
    assert len(verifying_backend.requests) == 1
    record = verifying_backend.requests[0]
    assert record["verified"] is False
    assert record["hmac_valid"] is False
    assert record["ed25519_valid"] is True


def test_backend_rejects_wrong_ed25519_seed(verifying_backend):
    code = _run_simulator(verifying_backend.base_url, ed25519_seed="22" * 32)
    assert code == 1
    assert len(verifying_backend.requests) == 1
    record = verifying_backend.requests[0]
    assert record["verified"] is False
    assert record["ed25519_valid"] is False
    assert record["hmac_valid"] is True
