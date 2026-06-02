"""
Health check endpoints for Kubernetes liveness/readiness probes.
"""
from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from celery.exceptions import TimeoutError

from soroscan.celery import app

WORKER_HEALTH_TIMEOUT_SECONDS = 2


@api_view(["GET"])
@permission_classes([AllowAny])
def health_view(request):
    """Liveness probe - app is running."""
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_view(request):
    """Readiness probe - DB and Redis are connected."""
    errors = []

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        errors.append(f"db: {str(e)}")

    try:
        cache.set("health_check", "1", timeout=10)
        if cache.get("health_check") != "1":
            errors.append("redis: failed to read value")
    except Exception as e:
        errors.append(f"redis: {str(e)}")

    if errors:
        return Response({"status": "not_ready", "errors": errors}, status=503)

    return Response({"status": "ready"})


@api_view(["GET"])
@permission_classes([AllowAny])
def worker_health_view(request):
    """Worker health probe - checks Celery workers are responding."""
    try:
        inspector = app.control.inspect(timeout=WORKER_HEALTH_TIMEOUT_SECONDS)
        worker_status = inspector.ping()

        if not worker_status:
            raise Exception("no worker responded")

        return Response({"status": "healthy", "workers": worker_status})
    except TimeoutError:
        return Response(
            {"status": "unhealthy", "error": "worker ping timeout"},
            status=503,
        )
    except Exception as exc:
        return Response(
            {"status": "unhealthy", "error": str(exc)},
            status=503,
        )
