"""Tests for the request latency percentile middleware (issue #1293)."""

import time
from types import SimpleNamespace

from django.test import RequestFactory, TestCase
from prometheus_client import REGISTRY

from soroscan.middleware import RequestLatencyMiddleware


class RequestLatencyMiddlewareTests(TestCase):
    def test_records_latency_histogram(self):
        def get_response(request):
            time.sleep(0.001)
            return SimpleNamespace(status_code=201)

        middleware = RequestLatencyMiddleware(get_response)
        request = RequestFactory().post("/api/v1/events/")
        request.resolver_match = SimpleNamespace(route="/api/v1/events/")
        middleware(request)

        value = REGISTRY.get_sample_value(
            "soroscan_request_latency_seconds_count",
            {"method": "POST", "endpoint": "/api/v1/events/", "status": "201"},
        )
        self.assertIsNotNone(value)
        self.assertGreaterEqual(value, 1.0)

    def test_falls_back_to_raw_path_without_resolver_match(self):
        def get_response(request):
            return SimpleNamespace(status_code=200)

        middleware = RequestLatencyMiddleware(get_response)
        request = RequestFactory().get("/healthz")
        # No resolver_match attached -> falls back to request.path
        middleware(request)

        value = REGISTRY.get_sample_value(
            "soroscan_request_latency_seconds_count",
            {"method": "GET", "endpoint": "/healthz", "status": "200"},
        )
        self.assertIsNotNone(value)
        self.assertGreaterEqual(value, 1.0)
