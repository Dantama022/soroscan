"""Tests for API-key authentication hygiene (issue #1699).

The ``APIKeyThrottle`` must read API keys **only** from the
``Authorization: ApiKey <token>`` header.  Query-string (``?api_key=``) and
request-body (``api_key=``) keys must be ignored because URLs and bodies are
routinely logged by proxies, servers, and analytics — leaking credentials.

These tests exercise ``APIKeyThrottle.get_ident`` directly, plus one end-to-end
call to ``allow_request`` for an invalid query-string-only key to confirm the
throttle does **not** see it.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from soroscan.throttles import APIKeyThrottle


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(*, header: str | None = None, query: dict | None = None, body: dict | None = None):
    """Build a DRF-ish request with header / GET / POST populated."""
    rf = RequestFactory()
    if body:
        request = rf.post("/api/ingest/record/", data=body)
    else:
        request = rf.get("/api/ingest/contracts/")
    if query:
        request.GET = request.GET.copy()
        request.GET.update(query)
    if header is not None:
        # RequestFactory converts this to HTTP_AUTHORIZATION in META
        request.META["HTTP_AUTHORIZATION"] = header
    return request


# ---------------------------------------------------------------------------
# get_ident() — header is the ONLY accepted source
# ---------------------------------------------------------------------------

class TestGetIdentHeaderOnly:
    def test_returns_token_from_authorization_header(self):
        throttle = APIKeyThrottle()
        request = _make_request(header="ApiKey sk_live_ABC123")
        assert throttle.get_ident(request) == "sk_live_ABC123"

    def test_scheme_is_case_insensitive(self):
        throttle = APIKeyThrottle()
        request = _make_request(header="apikey sk_live_ABC123")
        assert throttle.get_ident(request) == "sk_live_ABC123"

    def test_extra_whitespace_after_scheme_is_stripped(self):
        throttle = APIKeyThrottle()
        request = _make_request(header="ApiKey    sk_live_ABC123   ")
        assert throttle.get_ident(request) == "sk_live_ABC123"

    def test_query_string_api_key_is_ignored(self):
        """Regression for #1699 — ?api_key= must not authenticate."""
        throttle = APIKeyThrottle()
        request = _make_request(query={"api_key": "sk_live_QUERY"})
        assert throttle.get_ident(request) is None

    def test_body_api_key_is_ignored(self):
        """Regression for #1699 — POST api_key= must not authenticate."""
        throttle = APIKeyThrottle()
        request = _make_request(body={"api_key": "sk_live_BODY"})
        assert throttle.get_ident(request) is None

    def test_query_and_body_ignored_even_when_header_also_present(self):
        """Header wins; the query/body values are never consulted."""
        throttle = APIKeyThrottle()
        request = _make_request(
            header="ApiKey sk_live_HEADER",
            query={"api_key": "sk_live_QUERY"},
            body={"api_key": "sk_live_BODY"},
        )
        assert throttle.get_ident(request) == "sk_live_HEADER"

    def test_wrong_scheme_is_rejected(self):
        """Only the ApiKey scheme is accepted (e.g. `Bearer` is not)."""
        throttle = APIKeyThrottle()
        request = _make_request(header="Bearer sk_live_ABC123")
        assert throttle.get_ident(request) is None

    def test_malformed_header_without_token_is_rejected(self):
        throttle = APIKeyThrottle()
        request = _make_request(header="ApiKey")
        assert throttle.get_ident(request) is None

    def test_empty_header_is_rejected(self):
        throttle = APIKeyThrottle()
        request = _make_request(header="")
        assert throttle.get_ident(request) is None


# ---------------------------------------------------------------------------
# allow_request() — query/body keys do not drive the quota accounting
# ---------------------------------------------------------------------------

class TestAllowRequestHeaderOnly:
    def test_no_header_and_no_query_key_allows_request(self):
        """No credential at all → throttle defers to other throttles (returns True)."""
        throttle = APIKeyThrottle()
        request = _make_request()
        view = SimpleNamespace(kwargs={})
        assert throttle.allow_request(request, view) is True

    def test_query_string_key_does_not_trigger_rejection(self):
        """A bogus ?api_key= must not cause a 401 / False — it's simply ignored."""
        throttle = APIKeyThrottle()
        request = _make_request(query={"api_key": "sk_live_SHOULD_NOT_BE_USED"})
        view = SimpleNamespace(kwargs={})
        # No header → get_ident() is None → allow_request short-circuits True
        assert throttle.allow_request(request, view) is True

    def test_body_key_does_not_trigger_rejection(self):
        throttle = APIKeyThrottle()
        request = _make_request(body={"api_key": "sk_live_SHOULD_NOT_BE_USED"})
        view = SimpleNamespace(kwargs={})
        assert throttle.allow_request(request, view) is True