import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from soroscan.webhook_verification import verify_webhook_signature


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_keypair():
    """Return (private_key, public_key_b64) for a fresh Ed25519 key pair."""
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    return priv, pub_b64


def _sign(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    """Return a well-formed ``ed25519=<base64>`` signature header value."""
    return "ed25519=" + base64.b64encode(private_key.sign(payload)).decode("ascii")


# ---------------------------------------------------------------------------
# Positive case (retained from original)
# ---------------------------------------------------------------------------

def test_sdk_verify_webhook_signature():
    payload = b'{"hello":"world"}'
    private_key = Ed25519PrivateKey.generate()
    signature = base64.b64encode(private_key.sign(payload)).decode("ascii")
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    assert verify_webhook_signature(payload, f"ed25519={signature}", public_key)


# ---------------------------------------------------------------------------
# Failure paths — #1670
# ---------------------------------------------------------------------------

def test_tampered_payload_returns_false():
    """Modifying the payload after signing must fail verification."""
    priv, pub_b64 = _make_keypair()
    original_payload = b'{"event":"transfer","amount":"100"}'
    sig_header = _sign(priv, original_payload)

    tampered_payload = b'{"event":"transfer","amount":"999"}'
    assert verify_webhook_signature(tampered_payload, sig_header, pub_b64) is False


def test_wrong_signature_returns_false():
    """A signature produced by a different key must not verify."""
    _, pub_b64 = _make_keypair()
    wrong_priv, _ = _make_keypair()  # completely unrelated key pair

    payload = b'{"event":"ping"}'
    sig_header = _sign(wrong_priv, payload)

    assert verify_webhook_signature(payload, sig_header, pub_b64) is False


def test_missing_prefix_returns_false():
    """A header without the ``ed25519=`` prefix must be rejected."""
    priv, pub_b64 = _make_keypair()
    payload = b'{"event":"ping"}'
    raw_sig = base64.b64encode(priv.sign(payload)).decode("ascii")

    # No prefix at all
    assert verify_webhook_signature(payload, raw_sig, pub_b64) is False


def test_wrong_prefix_returns_false():
    """A header with a different algorithm prefix (e.g. sha256=) must be rejected."""
    priv, pub_b64 = _make_keypair()
    payload = b'{"event":"ping"}'
    raw_sig = base64.b64encode(priv.sign(payload)).decode("ascii")

    assert verify_webhook_signature(payload, f"sha256={raw_sig}", pub_b64) is False


def test_empty_header_returns_false():
    """An empty signature header must return False, not raise."""
    _, pub_b64 = _make_keypair()
    assert verify_webhook_signature(b'{"event":"ping"}', "", pub_b64) is False


def test_malformed_base64_signature_returns_false():
    """Non-base64 characters after the prefix must return False, not raise."""
    _, pub_b64 = _make_keypair()
    payload = b'{"event":"ping"}'
    assert verify_webhook_signature(payload, "ed25519=!!!not_valid_base64!!!", pub_b64) is False


def test_malformed_base64_public_key_returns_false():
    """A public key that cannot be base64-decoded must return False, not raise."""
    priv, _ = _make_keypair()
    payload = b'{"event":"ping"}'
    sig_header = _sign(priv, payload)

    assert verify_webhook_signature(payload, sig_header, "!!!not_valid_base64!!!") is False


def test_wrong_length_public_key_returns_false():
    """A base64-encoded blob of the wrong byte length is not a valid Ed25519 key."""
    priv, _ = _make_keypair()
    payload = b'{"event":"ping"}'
    sig_header = _sign(priv, payload)

    # 10 bytes — far too short for an Ed25519 public key (must be 32 bytes)
    bad_pub = base64.b64encode(b"\x00" * 10).decode("ascii")
    assert verify_webhook_signature(payload, sig_header, bad_pub) is False


def test_truncated_signature_returns_false():
    """A base64 value that decodes to fewer bytes than a valid Ed25519 signature must fail."""
    _, pub_b64 = _make_keypair()
    payload = b'{"event":"ping"}'
    # 8 bytes — far shorter than the 64-byte Ed25519 signature
    short_sig = base64.b64encode(b"\x00" * 8).decode("ascii")
    assert verify_webhook_signature(payload, f"ed25519={short_sig}", pub_b64) is False


@pytest.mark.parametrize("header", [
    "ed25519=",                     # prefix only, empty signature
    "ed25519= ",                    # prefix + whitespace
    "ED25519=abc",                  # wrong case on prefix
    "ed25519=abc==def",             # embedded padding in wrong place
])
def test_various_malformed_headers_return_false(header: str):
    """A range of syntactically malformed header values must all return False."""
    _, pub_b64 = _make_keypair()
    assert verify_webhook_signature(b'{"event":"ping"}', header, pub_b64) is False
