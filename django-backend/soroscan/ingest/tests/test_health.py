import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient



@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestHealthView:
    def test_health_returns_ok(self, api_client):
        url = reverse("health")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"status": "ok"}
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION


@pytest.mark.django_db
class TestReadinessView:
    def test_ready_when_db_and_cache_connected(self, api_client):
        url = reverse("readiness")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"status": "ready"}
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_not_ready_when_db_fails(self, api_client, monkeypatch):
        from django.db import connection

        def mocked_cursor(*args, **kwargs):
            raise Exception("DB connection failed")

        monkeypatch.setattr(connection, "cursor", lambda: mocked_cursor())

        url = reverse("readiness")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not_ready"
        assert any("db" in e for e in response.data["errors"])
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION

    def test_not_ready_when_cache_fails(self, api_client, monkeypatch):
        def mocked_get(*args, **kwargs):
            raise Exception("Cache connection failed")

        monkeypatch.setattr(cache, "get", mocked_get)

        url = reverse("readiness")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not_ready"
        assert any("redis" in e for e in response.data["errors"])
        assert response["X-SoroScan-Version"] == settings.SOFTWARE_VERSION


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