import hashlib
import hmac
import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from soroscan.ingest.tests.factories import (
    TrackedContractFactory,
    WebhookSubscriptionFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestWebhookHMACDecorator:
    def setup_method(self):
        self.contract = TrackedContractFactory()
        self.webhook = WebhookSubscriptionFactory(
            contract=self.contract,
            secret="test-secret-123",
            signature_algorithm="sha256",
        )
        self.url = reverse("webhook-receiver-example")

    def test_valid_sha256_signature(self, api_client):
        payload = {
            "contract_id": self.contract.contract_id,
            "event_type": "transfer",
            "payload": {"amount": 100},
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = hmac.new(b"test-secret-123", payload_bytes, hashlib.sha256).hexdigest()

        headers = {"X-SoroScan-Signature": f"sha256={sig}"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "verified"

    def test_valid_sha1_signature(self, api_client):
        self.webhook.signature_algorithm = "sha1"
        self.webhook.save()

        payload = {
            "contract_id": self.contract.contract_id,
            "event_type": "transfer",
            "payload": {"amount": 100},
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = hmac.new(b"test-secret-123", payload_bytes, hashlib.sha1).hexdigest()

        headers = {"X-SoroScan-Signature": f"sha1={sig}"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "verified"

    def test_invalid_signature(self, api_client):
        payload = {"contract_id": self.contract.contract_id, "event_type": "transfer"}
        headers = {"X-SoroScan-Signature": "sha256=invalid-sig"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid HMAC signature" in response.data["detail"]

    def test_missing_signature_header(self, api_client):
        payload = {"contract_id": self.contract.contract_id}
        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing signature header" in response.data["detail"]

    def test_missing_contract_id(self, api_client):
        payload = {"event_type": "transfer"}
        headers = {"X-SoroScan-Signature": "sha256=some-sig"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing contract_id" in response.data["detail"]

    def test_inactive_subscription(self, api_client):
        self.webhook.is_active = False
        self.webhook.save()

        payload = {"contract_id": self.contract.contract_id}
        headers = {"X-SoroScan-Signature": "sha256=some-sig"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Subscription not found or inactive" in response.data["detail"]

    def test_multiple_subscriptions_one_matches(self, api_client):
        # Create another webhook for same contract with different secret
        WebhookSubscriptionFactory(
            contract=self.contract, secret="other-secret", signature_algorithm="sha256"
        )

        payload = {"contract_id": self.contract.contract_id, "event_type": "transfer"}
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        # Sign with the first secret
        sig = hmac.new(b"test-secret-123", payload_bytes, hashlib.sha256).hexdigest()

        headers = {"X-SoroScan-Signature": f"sha256={sig}"}
        response = api_client.post(self.url, payload, format="json", headers=headers)

        assert response.status_code == status.HTTP_200_OK
