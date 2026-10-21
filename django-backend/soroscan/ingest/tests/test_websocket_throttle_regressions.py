"""Regression coverage for #1698 WebSocket parsing and #1704 throttle counters."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase
from prometheus_client import REGISTRY

from soroscan.ingest.consumers import EventConsumer
from soroscan.ingest.models import APIKey
from soroscan.throttles import APIKeyThrottle


def metric_value(reason):
    return REGISTRY.get_sample_value(
        "soroscan_throttle_rejections_total", {"reason": reason}
    ) or 0.0


class EventTypeQueryTests(SimpleTestCase):
    """No database or WebSocket server is required to exercise connect()."""

    def connect_with_query(self, query):
        consumer = EventConsumer()
        consumer.scope = {
            "url_route": {"kwargs": {"contract_id": "CEXAMPLE"}},
            "query_string": query,
        }
        consumer.channel_name = "test-channel"
        consumer.channel_layer = SimpleNamespace(group_add=AsyncMock())
        consumer.get_contract = AsyncMock(return_value=object())
        consumer.accept = AsyncMock()
        asyncio.run(consumer.connect())
        consumer.accept.assert_awaited_once()
        return consumer.event_type

    def test_event_type_with_other_query_parameters(self):
        self.assertEqual(
            self.connect_with_query(b"after=123&event_type=transfer&limit=10"),
            "transfer",
        )

    def test_event_type_decodes_url_escaping(self):
        self.assertEqual(
            self.connect_with_query(b"event_type=asset%2Ftransfer+updated"),
            "asset/transfer updated",
        )

    def test_repeated_event_type_uses_first_value(self):
        self.assertEqual(
            self.connect_with_query(b"event_type=created&event_type=deleted"),
            "created",
        )

    def test_missing_and_blank_event_type_mean_no_filter(self):
        self.assertIsNone(self.connect_with_query(b"limit=10"))
        self.assertIsNone(self.connect_with_query(b"event_type="))
        self.assertIsNone(self.connect_with_query(b"other=event_type%3Dfoo"))


class APIKeyThrottleMetricTests(SimpleTestCase):
    def request(self, token="fake-key", api_key=None):
        return SimpleNamespace(
            META={"HTTP_AUTHORIZATION": f"ApiKey {token}" if token else ""},
            GET={}, POST={}, data={}, api_key=api_key,
        )

    def test_invalid_key_increments_only_its_reason(self):
        before = metric_value("invalid_api_key")
        quota_before = metric_value("quota_exhausted")
        with patch.object(APIKey.objects, "select_related") as related:
            related.return_value.get.side_effect = APIKey.DoesNotExist
            allowed = APIKeyThrottle().allow_request(
                self.request(), SimpleNamespace(kwargs={})
            )
        self.assertFalse(allowed)
        self.assertEqual(metric_value("invalid_api_key"), before + 1)
        self.assertEqual(metric_value("quota_exhausted"), quota_before)

    def test_exhausted_quota_increments_only_its_reason(self):
        before = metric_value("quota_exhausted")
        other_before = metric_value("invalid_api_key")
        key = SimpleNamespace(id=42, pk=42, quota_per_hour=2)
        with patch("soroscan.throttles.cache.get", return_value=2):
            allowed = APIKeyThrottle().allow_request(
                self.request(api_key=key), SimpleNamespace(kwargs={})
            )
        self.assertFalse(allowed)
        self.assertEqual(metric_value("quota_exhausted"), before + 1)
        self.assertEqual(metric_value("invalid_api_key"), other_before)

    def test_requests_without_key_are_not_counted(self):
        invalid_before = metric_value("invalid_api_key")
        quota_before = metric_value("quota_exhausted")
        self.assertTrue(
            APIKeyThrottle().allow_request(
                self.request(token=""), SimpleNamespace(kwargs={})
            )
        )
        self.assertEqual(metric_value("invalid_api_key"), invalid_before)
        self.assertEqual(metric_value("quota_exhausted"), quota_before)
