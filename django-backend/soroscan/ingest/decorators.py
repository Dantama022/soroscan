import hashlib
import hmac
import json
import logging
from functools import wraps

from rest_framework import status
from rest_framework.response import Response

from .models import WebhookSubscription

logger = logging.getLogger(__name__)


def webhook_hmac_required(header_name="X-SoroScan-Signature"):
    """
    DRF view decorator that validates an incoming webhook's HMAC signature.

    The decorator expects the JSON payload to contain a 'contract_id' field,
    which is used to look up the corresponding WebhookSubscription(s) and their secrets.
    The signature is verified against the serialized JSON body using hmac.compare_digest.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            signature_header = request.headers.get(header_name)
            if not signature_header:
                logger.warning("Missing webhook signature header: %s", header_name)
                return Response(
                    {"detail": f"Missing signature header {header_name}"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if "=" not in signature_header:
                logger.warning("Invalid signature header format: %s", signature_header)
                return Response(
                    {"detail": "Invalid signature header format"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            prefix, sig_hex = signature_header.split("=", 1)
            prefix = prefix.lower()

            try:
                # DRF parses the JSON body into request.data
                payload = request.data
                contract_id = payload.get("contract_id")
            except Exception:
                logger.warning("Failed to parse request data for HMAC validation")
                return Response(
                    {"detail": "Invalid JSON payload"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not contract_id:
                logger.warning("Missing contract_id in webhook payload")
                return Response(
                    {"detail": "Missing contract_id in payload"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Find active subscriptions for this contract
            subscriptions = WebhookSubscription.objects.filter(
                contract__contract_id=contract_id, is_active=True
            )

            if not subscriptions.exists():
                logger.warning(
                    "No active webhook subscription found for contract: %s", contract_id
                )
                return Response(
                    {"detail": "Subscription not found or inactive"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Re-serialize exactly as the dispatcher does (sort_keys=True, utf-8)
            # This ensures we are testing against the same byte sequence used for signing.
            try:
                payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            except (TypeError, ValueError) as exc:
                logger.error("Failed to re-serialize payload for HMAC check: %s", exc)
                return Response(
                    {"detail": "Payload serialization failed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if prefix == "sha256":
                digestmod = hashlib.sha256
            elif prefix == "sha1":
                digestmod = hashlib.sha1
            else:
                logger.warning("Unsupported signature algorithm: %s", prefix)
                return Response(
                    {"detail": f"Unsupported signature algorithm: {prefix}"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            verified = False
            for sub in subscriptions:
                # Verify secret exists
                if not sub.secret:
                    continue

                expected_sig = hmac.new(
                    sub.secret.encode("utf-8"),
                    msg=payload_bytes,
                    digestmod=digestmod,
                ).hexdigest()

                if hmac.compare_digest(expected_sig, sig_hex):
                    verified = True
                    request.webhook_subscription = sub
                    break

            if not verified:
                logger.warning("HMAC signature mismatch for contract: %s", contract_id)
                return Response(
                    {"detail": "Invalid HMAC signature"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
