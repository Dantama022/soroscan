"""
Health check endpoints for Kubernetes liveness/readiness probes.
"""
import time

from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


PROCESS_START_TIME = time.monotonic()


def format_uptime(seconds: int) -> str:
    """Format uptime seconds as DH:M:S."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{days}D:{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_uptime_payload() -> dict:
    """Return machine-readable and human-readable uptime values."""
    uptime_seconds = max(0, int(time.monotonic() - PROCESS_START_TIME))

    return {
        "uptime_seconds": uptime_seconds,
        "uptime": format_uptime(uptime_seconds),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def health_view(request):
    """Liveness probe - app is running."""
    return Response(
        {
            "status": "ok",
            **get_uptime_payload(),
        }
    )


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