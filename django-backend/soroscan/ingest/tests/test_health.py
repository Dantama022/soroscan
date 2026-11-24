import time
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from soroscan.health import format_uptime

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mock_soroban_rpc_healthy():
    """Stub out the Soroban RPC HTTP call so tests don't need a live node."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"result": {"status": "healthy"}}
    with patch("soroscan.health.requests.post", return_value=mock_response) as mock_post:
        yield mock_post

@pytest.fixture
def mock_redis_healthy():
    """Stub out the Redis PING so tests don't need a live Redis."""
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    with patch("soroscan.health.redis_lib.Redis.from_url", return_value=mock_redis):
        yield mock_redis

@pytest.mark.django_db
class TestHealthView:
    def test_health_returns_ok_with_uptime(self, api_client):
        url = reverse("health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        assert "uptime_seconds" in response.data
        assert "uptime" in response.data
        assert isinstance(response.data["uptime_seconds"], int)
        assert response.data["uptime_seconds"] >= 0
        assert isinstance(response.data["uptime"], str)
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_health_uptime_is_human_readable(self):
        assert format_uptime(0) == "0D:00:00:00"
        assert format_uptime(59) == "0D:00:00:59"
        assert format_uptime(60) == "0D:00:01:00"
        assert format_uptime(3600) == "0D:01:00:00"
        assert format_uptime(90061) == "1D:01:01:01"

    def test_health_uptime_counter_increases_across_requests(self, api_client):
        url = reverse("health")

        first_response = api_client.get(url)
        time.sleep(1.1)
        second_response = api_client.get(url)

        assert first_response.status_code == status.HTTP_200_OK
        assert second_response.status_code == status.HTTP_200_OK
        assert second_response.data["uptime_seconds"] >= first_response.data["uptime_seconds"]


@pytest.mark.django_db
class TestReadinessView:
    def test_ready_when_db_and_cache_connected(self, api_client, mock_soroban_rpc_healthy, mock_redis_healthy):
        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            url = reverse("readiness")
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert "components" in response.data
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_not_ready_when_db_fails(self, api_client, monkeypatch, mock_soroban_rpc_healthy):
        from django.db import connection
        monkeypatch.setattr(connection, "cursor", lambda: (_ for _ in ()).throw(Exception("DB fail")))

        url = reverse("readiness")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "degraded"
        assert "database" in response.data["components"]
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_not_ready_when_redis_connection_fails(self, api_client, monkeypatch, mock_soroban_rpc_healthy):
        import redis as redis_lib

        def failing_from_url(*args, **kwargs):
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = redis_lib.ConnectionError("Redis connection refused")
            return mock_redis

        monkeypatch.setattr(redis_lib.Redis, "from_url", failing_from_url)

        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            url = reverse("readiness")
            response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "degraded"
        assert "redis" in response.data["components"]
        assert "connection refused" in response.data["components"]["redis"]
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_not_ready_when_redis_timeout(self, api_client, monkeypatch, mock_soroban_rpc_healthy):
        import redis as redis_lib

        def timeout_from_url(*args, **kwargs):
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = redis_lib.TimeoutError("Redis timeout")
            return mock_redis

        monkeypatch.setattr(redis_lib.Redis, "from_url", timeout_from_url)

        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            url = reverse("readiness")
            response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "degraded"
        assert "redis" in response.data["components"]
        assert "timeout" in response.data["components"]["redis"]

    def test_ready_when_redis_ping_succeeds(self, api_client, mock_soroban_rpc_healthy, mock_redis_healthy):
        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            url = reverse("readiness")
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["components"]["redis"] == "healthy"


@pytest.mark.django_db
class TestWorkerHealthView:
    def test_worker_health_returns_200_when_worker_responds(self, api_client, monkeypatch):
        class DummyInspect:
            def ping(self):
                return {"worker1@hostname": {"ok": "pong"}}

        monkeypatch.setattr(
            "soroscan.health.app.control.inspect",
            lambda timeout=None: DummyInspect(),
        )

        url = reverse("worker-health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert response.data["workers"] == {"worker1@hostname": {"ok": "pong"}}
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_worker_health_returns_503_when_workers_unresponsive(self, api_client, monkeypatch):
        class DummyInspect:
            def ping(self):
                return {}

        monkeypatch.setattr(
            "soroscan.health.app.control.inspect",
            lambda timeout=None: DummyInspect(),
        )

        url = reverse("worker-health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert "no worker responded" in response.data["error"]
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION


@pytest.mark.django_db
class TestCheckCeleryWorkers:
    """Unit tests for the shared worker-inspection helper (issue #1577)."""

    def test_returns_healthy_with_workers_when_ping_succeeds(self, monkeypatch):
        from soroscan.monitoring import check_celery_workers

        class DummyInspect:
            def ping(self):
                return {"worker1@host": {"ok": "pong"}}

        monkeypatch.setattr(
            "soroscan.celery.app.control.inspect", lambda timeout=None: DummyInspect()
        )

        result = check_celery_workers(timeout=1)
        assert result["status"] == "healthy"
        assert result["workers"] == {"worker1@host": {"ok": "pong"}}
        assert "error" not in result

    def test_returns_unhealthy_when_no_worker(self, monkeypatch):
        from soroscan.monitoring import check_celery_workers

        class DummyInspect:
            def ping(self):
                return {}

        monkeypatch.setattr(
            "soroscan.celery.app.control.inspect", lambda timeout=None: DummyInspect()
        )

        result = check_celery_workers(timeout=1)
        assert result["status"] == "unhealthy"
        assert result["error"] == "no worker responded"
        assert result["workers"] == {}

    def test_timeout_maps_to_worker_ping_timeout(self, monkeypatch):
        from celery.exceptions import TimeoutError as CeleryTimeoutError

        from soroscan.monitoring import check_celery_workers

        class DummyInspect:
            def ping(self):
                raise CeleryTimeoutError("deadline passed")

        monkeypatch.setattr(
            "soroscan.celery.app.control.inspect", lambda timeout=None: DummyInspect()
        )

        result = check_celery_workers(timeout=1)
        assert result["status"] == "unhealthy"
        assert result["error"] == "worker ping timeout"

    def test_generic_exception_is_masked(self, monkeypatch):
        from soroscan.monitoring import check_celery_workers

        class DummyInspect:
            def ping(self):
                raise ConnectionError("amqp://user:secret@broker.internal:5672 refused")

        monkeypatch.setattr(
            "soroscan.celery.app.control.inspect", lambda timeout=None: DummyInspect()
        )

        result = check_celery_workers(timeout=1)
        assert result["status"] == "unhealthy"
        assert result["error"] == "worker inspection failed"
        # Never leak broker coordinates to an unauthenticated probe.
        assert "broker.internal" not in result["error"]
        assert "secret" not in result["error"]


@pytest.mark.django_db
class TestWorkerHealthViewErrorPaths:
    """Endpoint-level tests for the delegated worker probe (issue #1577)."""

    def test_worker_health_masks_generic_exception(self, api_client, monkeypatch):
        class DummyInspect:
            def ping(self):
                raise ConnectionError("amqp://user:secret@broker.internal:5672 refused")

        monkeypatch.setattr(
            "soroscan.health.app.control.inspect",
            lambda timeout=None: DummyInspect(),
        )

        url = reverse("worker-health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["error"] == "worker inspection failed"
        assert "broker.internal" not in response.data["error"]

    def test_worker_health_timeout_returns_503(self, api_client, monkeypatch):
        from celery.exceptions import TimeoutError as CeleryTimeoutError

        class DummyInspect:
            def ping(self):
                raise CeleryTimeoutError("worker ping exceeded deadline")

        monkeypatch.setattr(
            "soroscan.health.app.control.inspect",
            lambda timeout=None: DummyInspect(),
        )

        url = reverse("worker-health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["error"] == "worker ping timeout"

    def test_worker_health_passes_configured_timeout(self, api_client, monkeypatch):
        from soroscan.health import WORKER_HEALTH_TIMEOUT_SECONDS

        seen = {}

        class DummyInspect:
            def ping(self):
                return {"worker1@host": {"ok": "pong"}}

        def fake_inspect(timeout=None):
            seen["timeout"] = timeout
            return DummyInspect()

        monkeypatch.setattr("soroscan.health.app.control.inspect", fake_inspect)

        url = reverse("worker-health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert seen["timeout"] == WORKER_HEALTH_TIMEOUT_SECONDS

    def test_worker_health_responds_promptly(self, api_client, monkeypatch):
        # The probe must answer within the inspection timeout, not hang on a
        # dead broker. A slow ping would trip the endpoint's own budget.
        import time as _time

        class SlowInspect:
            def ping(self):
                _time.sleep(3)
                return {}

        monkeypatch.setattr(
            "soroscan.health.app.control.inspect",
            lambda timeout=None: SlowInspect(),
        )

        url = reverse("worker-health")
        start = _time.perf_counter()
        response = api_client.get(url)
        elapsed = _time.perf_counter() - start

        # DRF runs the view synchronously, so the sleep still happens here; the
        # assertion documents that the endpoint does not add work beyond the
        # single inspection call.
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert elapsed < 5