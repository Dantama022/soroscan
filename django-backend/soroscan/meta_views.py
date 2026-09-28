"""
Administrative meta endpoints for SoroScan (issue #1289).

Exposes:
- ``GET /api/meta/db-pool/``  — real-time DB connection stats + configured
  pool limits, behind admin-only authentication.
- ``POST /api/meta/db-pool/emit-metrics/`` — trigger on-demand Prometheus
  metric collection from pg_stat_activity.

These endpoints help operators detect connection leaks, pool exhaustion, and
configure autoscaling without exposing raw database credentials.
"""
import logging

from django.db import connections
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from soroscan.db_pool import DB_POOL_SETTINGS, emit_pool_metrics

logger = logging.getLogger(__name__)


def _collect_postgres_pool_stats(conn_wrapper):
    """Collect live connection metrics from PostgreSQL system views."""
    with conn_wrapper.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE datname = current_database()) AS total,
                COUNT(*) FILTER (
                    WHERE datname = current_database() AND state = 'active'
                ) AS active,
                COUNT(*) FILTER (
                    WHERE datname = current_database() AND state = 'idle'
                ) AS idle,
                COUNT(*) FILTER (
                    WHERE datname = current_database()
                    AND wait_event_type IS NOT NULL
                ) AS wait_queue,
                COUNT(*) FILTER (
                    WHERE datname = current_database()
                    AND state = 'idle in transaction'
                ) AS idle_in_transaction,
                MAX(EXTRACT(EPOCH FROM (now() - query_start)))
                    FILTER (WHERE datname = current_database() AND state = 'active')
                    AS longest_query_seconds
            FROM pg_stat_activity
            """
        )
        row = cursor.fetchone()

    total, active, idle, wait_queue, idle_in_txn, longest_q = row

    return {
        "total": int(total or 0),
        "active": int(active or 0),
        "idle": int(idle or 0),
        "wait_queue": int(wait_queue or 0),
        "idle_in_transaction": int(idle_in_txn or 0),
        "longest_active_query_seconds": (
            round(float(longest_q), 2) if longest_q is not None else None
        ),
    }


def _collect_fallback_pool_stats(conn_wrapper):
    """Fallback for non-PostgreSQL test/dev databases without pool metadata."""
    conn_wrapper.ensure_connection()
    is_usable = conn_wrapper.is_usable()
    return {
        "total": 1,
        "active": 0 if is_usable else 1,
        "idle": 1 if is_usable else 0,
        "wait_queue": 0,
        "idle_in_transaction": 0,
        "longest_active_query_seconds": None,
    }


@extend_schema(
    responses=inline_serializer(
        name="DbPoolStatsResponse",
        fields={
            "live": inline_serializer(
                name="DbPoolLiveStats",
                fields={
                    "total": serializers.IntegerField(
                        help_text="Total live connections for the current database."
                    ),
                    "active": serializers.IntegerField(
                        help_text="Live connections currently executing queries."
                    ),
                    "idle": serializers.IntegerField(
                        help_text="Live connections currently idle."
                    ),
                    "wait_queue": serializers.IntegerField(
                        help_text="Live connections waiting on a database wait event."
                    ),
                    "idle_in_transaction": serializers.IntegerField(
                        help_text="Connections in idle-in-transaction state (potential leaks)."
                    ),
                    "longest_active_query_seconds": serializers.FloatField(
                        allow_null=True,
                        help_text="Wall-clock age of the longest running active query, or null.",
                    ),
                },
            ),
            "config": inline_serializer(
                name="DbPoolConfig",
                fields={
                    "pool_min": serializers.IntegerField(
                        help_text="Configured minimum pool size."
                    ),
                    "pool_max": serializers.IntegerField(
                        help_text="Configured maximum pool size."
                    ),
                    "conn_max_age": serializers.IntegerField(
                        help_text="Django CONN_MAX_AGE setting (seconds)."
                    ),
                    "statement_timeout_ms": serializers.IntegerField(
                        help_text="PostgreSQL statement timeout (milliseconds)."
                    ),
                },
            ),
        },
    ),
    description=(
        "Return real-time database connection pool statistics for the default "
        "database alias, plus the configured pool limits.  Useful for detecting "
        "connection leaks or pool exhaustion.  **Admin (staff) access required.**"
    ),
    tags=["meta"],
    auth=["jwtAuth"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def db_pool_stats_view(request):
    """
    Return real-time DB connection-pool stats for the ``default`` alias.

    The caller must be an active staff/superuser (Django ``is_staff=True``).
    Regular authenticated users receive a 403 Forbidden.

    Response keys
    -------------
    live.total                        – total live DB connections for the current database
    live.active                       – live connections currently executing queries
    live.idle                         – live connections currently idle
    live.wait_queue                   – live connections waiting on a DB wait event
    live.idle_in_transaction          – connections in idle-in-transaction (possible leaks)
    live.longest_active_query_seconds – wall-clock age of the longest running active query
    config.pool_min                   – configured minimum pool size
    config.pool_max                   – configured maximum pool size
    config.conn_max_age               – Django CONN_MAX_AGE in seconds
    config.statement_timeout_ms       – PostgreSQL statement timeout
    """
    if not request.user.is_staff:
        return Response(
            {"detail": "Admin access required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    alias = "default"
    conn_wrapper = connections[alias]

    try:
        if conn_wrapper.vendor == "postgresql":
            live_stats = _collect_postgres_pool_stats(conn_wrapper)
        else:
            live_stats = _collect_fallback_pool_stats(conn_wrapper)

    except Exception:  # pragma: no cover — only fires on genuine DB outage
        logger.exception("Failed to retrieve DB pool stats for alias '%s'", alias)
        return Response(
            {"detail": "Could not retrieve database connection pool statistics."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    config = {
        "pool_min": DB_POOL_SETTINGS.get("_pool_min"),
        "pool_max": DB_POOL_SETTINGS.get("_pool_max"),
        "conn_max_age": DB_POOL_SETTINGS.get("_conn_max_age"),
        "statement_timeout_ms": DB_POOL_SETTINGS.get("_statement_timeout_ms"),
    }

    return Response({"live": live_stats, "config": config})


@extend_schema(
    responses=inline_serializer(
        name="DbPoolMetricsResponse",
        fields={
            "status": serializers.CharField(help_text="'ok' or 'error'"),
            "detail": serializers.CharField(help_text="Human-readable result message."),
        },
    ),
    description=(
        "Trigger an on-demand export of database connection pool metrics to "
        "Prometheus.  Normally metrics are refreshed by a Celery beat task every "
        "60 seconds; use this endpoint to force an immediate refresh.  "
        "**Admin (staff) access required.**"
    ),
    tags=["meta"],
    auth=["jwtAuth"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def db_pool_emit_metrics_view(request):
    """
    POST /api/meta/db-pool/emit-metrics/

    Force an on-demand collection of pg_stat_activity metrics to Prometheus.
    **Admin (staff) access required.**
    """
    if not request.user.is_staff:
        return Response(
            {"detail": "Admin access required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        emit_pool_metrics()
        return Response(
            {"status": "ok", "detail": "DB pool metrics emitted to Prometheus."},
            status=status.HTTP_200_OK,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("db_pool_emit_metrics_view: failed to emit metrics")
        return Response(
            {"status": "error", "detail": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
