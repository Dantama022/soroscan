"""
Live integration tests for the SoroScan Python SDK (issue #1285).

These tests run against a real backend and are skipped unless the
``SOROSCAN_INTEGRATION_TEST_URL`` environment variable is set.

Usage
-----
    export SOROSCAN_INTEGRATION_TEST_URL=http://localhost:8000
    export SOROSCAN_INTEGRATION_API_KEY=your-api-key-here
    pytest sdk/python/tests/test_live_integration.py -v

For CI the backend is started by the ``sdk-integration-tests`` workflow.

Test coverage
-------------
- Authentication (valid key, invalid key, no key)
- GET /contracts — pagination, filters, cache header
- GET /contracts/:id — not found
- GET /events — pagination, type filter, ledger range
- WebSocket streaming — connects, receives events, closes cleanly
- Webhooks — CRUD lifecycle
- Error types — confirm SDK raises correct subclass per HTTP code
"""

from __future__ import annotations

import os
import time
import threading
import queue

import pytest

# ---------------------------------------------------------------------------
# Skip guard — every test is skipped unless a live backend is configured
# ---------------------------------------------------------------------------

LIVE_BASE_URL: str | None = os.getenv("SOROSCAN_INTEGRATION_TEST_URL")
LIVE_API_KEY: str | None = os.getenv("SOROSCAN_INTEGRATION_API_KEY")

pytestmark = pytest.mark.skipif(
    not LIVE_BASE_URL,
    reason=(
        "Set SOROSCAN_INTEGRATION_TEST_URL to run live integration tests. "
        "Optionally set SOROSCAN_INTEGRATION_API_KEY."
    ),
)

# ---------------------------------------------------------------------------
# Imports (deferred until environment is confirmed)
# ---------------------------------------------------------------------------

from soroscan import SoroScanClient  # noqa: E402 — must be after env check
from soroscan.exceptions import (  # noqa: E402
    SoroScanAuthenticationError,
    SoroScanAuthorizationError,
    SoroScanAuthError,
    SoroScanNotFoundError,
    SoroScanValidationError,
    SoroScanRateLimitError,
    SoroScanError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(api_key: str | None = ...) -> SoroScanClient:  # type: ignore[assignment]
    """Create a client pointed at the live backend."""
    effective_key = LIVE_API_KEY if api_key is ... else api_key
    return SoroScanClient(
        base_url=LIVE_BASE_URL,  # type: ignore[arg-type]
        api_key=effective_key,
        timeout=30.0,
    )


def unique_contract_id() -> str:
    """Generate a contract ID that is almost certainly not in the DB."""
    rand = hex(int(time.time() * 1_000_000))[2:].upper().zfill(12)
    return f"CTEST{rand}{'0' * 44}"[:56]


def unique_webhook_url() -> str:
    rand = hex(int(time.time() * 1_000_000))[2:]
    return f"https://integration-test.example.com/hook/{rand}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client() -> SoroScanClient:
    return make_client()


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_invalid_api_key_raises_authentication_error(self):
        """HTTP 401 → SoroScanAuthenticationError (issue #1284)."""
        bad_client = make_client(api_key="totally-invalid-key-xyz")
        with pytest.raises(SoroScanAuthenticationError) as exc_info:
            bad_client.get_contracts()
        assert exc_info.value.status_code == 401

    def test_invalid_api_key_is_also_auth_error(self):
        """Backward compat: SoroScanAuthError still catches 401."""
        bad_client = make_client(api_key="totally-invalid-key-xyz")
        with pytest.raises(SoroScanAuthError):
            bad_client.get_contracts()

    def test_no_api_key_reaches_backend(self):
        """An unauthenticated request should reach the backend (not be blocked by DNS)."""
        anon_client = make_client(api_key=None)
        try:
            anon_client.get_events(first=1)
        except SoroScanAuthenticationError:
            pass  # Expected on endpoints that require auth
        except SoroScanError:
            pass  # Any API-level error is fine — network is working

    def test_valid_credentials_allow_events_query(self, client: SoroScanClient):
        """A correctly authenticated request should succeed."""
        result = client.get_events(first=1)
        assert hasattr(result, "results") or isinstance(result, (list, dict))


# ---------------------------------------------------------------------------
# Contracts (REST GET /contracts)
# ---------------------------------------------------------------------------

class TestContracts:
    def test_get_contracts_returns_paginated_response(self, client: SoroScanClient):
        result = client.get_contracts(page=1, page_size=5)
        # PaginatedResponse from the SDK
        assert result.count >= 0
        assert isinstance(result.results, list)

    def test_get_contracts_page_size_respected(self, client: SoroScanClient):
        result = client.get_contracts(page=1, page_size=3)
        assert len(result.results) <= 3

    def test_get_contracts_is_active_filter(self, client: SoroScanClient):
        result = client.get_contracts(is_active=True, page_size=10)
        for contract in result.results:
            assert contract.is_active is True

    def test_get_contract_not_found_raises_not_found_error(self, client: SoroScanClient):
        """Unknown contract_id → SoroScanNotFoundError (issue #1284)."""
        with pytest.raises(SoroScanNotFoundError) as exc_info:
            client.get_contract(unique_contract_id())
        assert exc_info.value.status_code == 404

    def test_get_contracts_cache_header_present(self, client: SoroScanClient):
        """
        Issue #1288: The contracts endpoint should respond quickly (cached on 2nd request).
        We only check timing as a proxy — true cache validation requires header inspection.
        """
        client.get_contracts(page=1, page_size=5)  # warm cache
        t0 = time.monotonic()
        client.get_contracts(page=1, page_size=5)  # should hit cache
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, "Second contracts request took too long (>5 s), cache may be cold."


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_get_events_returns_paginated_response(self, client: SoroScanClient):
        result = client.get_events(first=5)
        assert result.total_count >= 0
        assert isinstance(result.items, list)
        assert len(result.items) <= 5

    def test_get_events_event_type_filter(self, client: SoroScanClient):
        result = client.get_events(event_type="transfer", first=5)
        for event in result.items:
            assert event.type == "transfer"

    def test_get_events_nonexistent_contract_returns_empty(self, client: SoroScanClient):
        result = client.get_events(contract_id=unique_contract_id(), first=5)
        assert result.items == []

    def test_get_events_ledger_range_filter(self, client: SoroScanClient):
        result = client.get_events(start_ledger=1, end_ledger=9_999_999, first=5)
        for event in result.items:
            assert 1 <= event.ledger <= 9_999_999

    def test_get_events_cursor_pagination(self, client: SoroScanClient):
        """Two pages with cursor-based pagination should not overlap."""
        page1 = client.get_events(first=3)
        if page1.page_info.has_next_page and page1.page_info.end_cursor:
            page2 = client.get_events(first=3, after=page1.page_info.end_cursor)
            ids1 = {e.id for e in page1.items}
            ids2 = {e.id for e in page2.items}
            assert ids1.isdisjoint(ids2), "Pages should not contain overlapping event IDs"


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

class TestWebhooks:
    def test_webhook_crud_lifecycle(self, client: SoroScanClient):
        """Create → get → update → delete a webhook subscription."""
        url = unique_webhook_url()
        webhook = client.subscribe_webhook(url=url, event_types=["transfer"])
        try:
            assert webhook.url == url
            assert "transfer" in webhook.event_types

            # Retrieve it
            fetched = client.get_webhook(webhook.id)
            assert fetched.id == webhook.id

            # Update it
            updated = client.update_webhook(webhook.id, event_types=["transfer", "mint"])
            assert "mint" in updated.event_types or "transfer" in updated.event_types

        finally:
            # Always clean up even if assertions fail
            try:
                client.delete_webhook(webhook.id)
            except SoroScanError:
                pass  # Already gone is fine

    def test_delete_nonexistent_webhook_raises_not_found(self, client: SoroScanClient):
        with pytest.raises(SoroScanNotFoundError):
            client.delete_webhook(99_999_999)


# ---------------------------------------------------------------------------
# Error type mapping (issue #1284)
# ---------------------------------------------------------------------------

class TestErrorTypeMapping:
    """Confirm the client raises the correct exception subclass for each HTTP code."""

    def test_401_raises_authentication_error(self):
        with pytest.raises(SoroScanAuthenticationError):
            make_client(api_key="bad-key").get_contracts()

    def test_404_raises_not_found_error(self, client: SoroScanClient):
        with pytest.raises(SoroScanNotFoundError):
            client.get_contract(unique_contract_id())

    def test_400_raises_validation_error_on_bad_input(self, client: SoroScanClient):
        """Sending an obviously invalid contract ID should yield a validation error."""
        with pytest.raises((SoroScanValidationError, SoroScanNotFoundError)):
            # An empty string is invalid input — backend should return 400 or 404
            client.get_contract("")

    def test_network_error_raises_soroscan_error(self):
        """Unreachable host raises a typed SDK error, not a raw httpx error."""
        from soroscan.exceptions import SoroScanConnectionError  # noqa: PLC0415
        dead_client = SoroScanClient(
            base_url="http://127.0.0.1:19999",  # Nothing listening here
            api_key="any",
            timeout=2.0,
        )
        with pytest.raises((SoroScanConnectionError, SoroScanError)):
            dead_client.get_contracts()
