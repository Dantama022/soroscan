"""Tests for the ``first`` page-size validation on ``GET /v1/events`` (issue #1592).

The endpoint previously clamped ``first`` with ``min(int(...), 200)`` and fell
back to the default on any parse error. That meant a typo like ``?first=abc``
returned a silently mis-sized page, and a huge or negative value was quietly
reshaped rather than explained. These tests lock in the new contract:

* a non-integer ``first`` is rejected with 400 and a ``code``/``message`` body;
* an out-of-range ``first`` is clamped into ``0..200`` (not rejected), so
  existing SDK integrations that overshoot keep working;
* the default of 20 and the response shape are unchanged.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from soroscan.ingest.tests.factories import ContractEventFactory, TrackedContractFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def events():
    """Five events on one contract so pagination has something to slice."""
    contract = TrackedContractFactory()
    for _ in range(5):
        ContractEventFactory(contract=contract, event_type="swap")
    return contract


@pytest.mark.django_db
class TestListEventsFirstValidation:
    url = reverse("v1-events")

    def test_default_first_is_20(self, api_client, events):
        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        # Fewer than 20 events exist, so all are returned under the default.
        assert len(response.data["items"]) == 5

    def test_valid_first_is_honoured(self, api_client, events):
        response = api_client.get(self.url, {"first": 3})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["items"]) == 3
        assert response.data["totalCount"] == 5
        assert response.data["pageInfo"]["hasNextPage"] is True

    def test_non_integer_first_returns_400(self, api_client, events):
        response = api_client.get(self.url, {"first": "abc"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "INVALID_ARGUMENT"
        assert "first" in response.data["message"]

    def test_float_first_returns_400(self, api_client, events):
        response = api_client.get(self.url, {"first": "2.5"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "INVALID_ARGUMENT"

    def test_empty_first_returns_400(self, api_client, events):
        response = api_client.get(self.url, {"first": ""})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "INVALID_ARGUMENT"

    def test_first_above_max_is_clamped_to_200(self, api_client, events):
        response = api_client.get(self.url, {"first": 9999})

        assert response.status_code == status.HTTP_200_OK
        # Only 5 events exist; the clamp allows up to 200, so all are returned.
        assert len(response.data["items"]) == 5

    def test_first_zero_returns_empty_page(self, api_client, events):
        response = api_client.get(self.url, {"first": 0})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["items"] == []
        assert response.data["totalCount"] == 5
        assert response.data["pageInfo"]["startCursor"] is None
        assert response.data["pageInfo"]["endCursor"] is None

    def test_negative_first_returns_empty_page(self, api_client, events):
        # -1 clamps up to 0, which yields an empty page rather than a 500 from
        # negative slicing.
        response = api_client.get(self.url, {"first": -1})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["items"] == []

    def test_bad_first_does_not_leak_other_errors(self, api_client):
        # No events exist at all; a bad ``first`` must still 400 before any
        # queryset work happens.
        response = api_client.get(self.url, {"first": "not-a-number"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "items" not in response.data
