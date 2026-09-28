"""
Database connection pool configuration and lifecycle helpers (issue #1289).

Pool sizing strategy
--------------------
Django itself does not manage a persistent connection pool in the traditional
sense — each OS thread/process gets one persistent connection (controlled by
CONN_MAX_AGE).  However, when deploying behind a PgBouncer proxy or using
``django-db-geventpool`` / ``django-postgrespool2``, explicit min/max sizes
matter.

This module provides:

1. ``calculate_pool_limits`` — compute load-aware min/max targets based on
   worker count and tunable environment variables.
2. ``get_pool_config`` — build the complete ``OPTIONS`` dict ready for Django's
   ``DATABASES`` setting.
3. ``emit_pool_metrics`` — export live ``pg_stat_activity`` values to
   Prometheus for dashboarding and alerting.
4. ``DB_POOL_SETTINGS`` — importable constant containing the validated config.

Environment variables
---------------------
WEB_CONCURRENCY            : Number of Gunicorn/Celery workers (default 4)
DB_CONNECTIONS_PER_WORKER  : Connections each worker holds (default 4)
DB_POOL_MIN_SIZE           : Minimum persistent connections (default 2)
DB_POOL_HARD_LIMIT         : Absolute max across all workers (default 40)
CONN_MAX_AGE               : Django persistent-connection lifetime in s (default 60)
DB_STATEMENT_TIMEOUT_MS    : PostgreSQL statement timeout in ms (default 30000)
DB_POOL_IDLE_TIMEOUT_MS    : Idle connection timeout in ms (default 300000, 5 min)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core sizing function
# ---------------------------------------------------------------------------


def calculate_pool_limits(
    *,
    workers: int | None = None,
    connections_per_worker: int | None = None,
    minimum: int | None = None,
    hard_limit: int | None = None,
) -> tuple[int, int]:
    """Return load-aware (min, max) connection targets.

    Gunicorn/Celery process counts are the stable proxy for application load.
    The result is bounded so a scale-out event cannot exhaust PostgreSQL's
    max_connections.

    Parameters
    ----------
    workers:
        Number of application processes.  Defaults to ``WEB_CONCURRENCY``
        environment variable (default ``4``).
    connections_per_worker:
        Maximum connections each worker can hold simultaneously.  Defaults
        to ``DB_CONNECTIONS_PER_WORKER`` (default ``4``).
    minimum:
        Minimum pool size to pre-allocate.  Defaults to ``DB_POOL_MIN_SIZE``
        (default ``2``).
    hard_limit:
        Absolute ceiling across **all** processes.  Defaults to
        ``DB_POOL_HARD_LIMIT`` (default ``40``).

    Returns
    -------
    (min_size, max_size)
        Both values are integers bounded by [minimum, hard_limit].

    Examples
    --------
    >>> calculate_pool_limits(workers=8, connections_per_worker=4)
    (2, 32)
    >>> calculate_pool_limits(workers=8, connections_per_worker=4, hard_limit=20)
    (2, 20)
    """
    worker_count = workers or int(os.getenv("WEB_CONCURRENCY", "4"))
    per_worker = connections_per_worker or int(
        os.getenv("DB_CONNECTIONS_PER_WORKER", "4")
    )
    min_connections = minimum or int(os.getenv("DB_POOL_MIN_SIZE", "2"))
    maximum = hard_limit or int(os.getenv("DB_POOL_HARD_LIMIT", "40"))

    computed_max = max(min_connections, worker_count * per_worker)
    bounded_max = min(maximum, computed_max)
    bounded_min = min(min_connections, bounded_max)

    logger.debug(
        "Pool limits calculated: workers=%d per_worker=%d → min=%d max=%d",
        worker_count,
        per_worker,
        bounded_min,
        bounded_max,
    )
    return bounded_min, bounded_max


# ---------------------------------------------------------------------------
# Django DATABASES OPTIONS builder
# ---------------------------------------------------------------------------

def get_pool_config(
    *,
    workers: int | None = None,
    connections_per_worker: int | None = None,
    minimum: int | None = None,
    hard_limit: int | None = None,
) -> dict[str, Any]:
    """Return a ready-to-use ``OPTIONS`` dict for ``settings.DATABASES["default"]``.

    Compatible with both raw ``psycopg2`` (via ``options`` key for
    ``connect_kwargs``) and ``django-db-geventpool`` / ``django-postgrespool2``
    (which consume ``POOL_OPTIONS``).

    Returns
    -------
    dict with keys:
    - ``connect_timeout`` — TCP handshake timeout (10 s)
    - ``options``         — PostgreSQL GUC overrides (statement_timeout, etc.)
    - ``POOL_OPTIONS``    — If a pool library is installed: min/max/timeout
    - ``pool``            — psycopg3 async pool parameters (future-compat)
    """
    min_size, max_size = calculate_pool_limits(
        workers=workers,
        connections_per_worker=connections_per_worker,
        minimum=minimum,
        hard_limit=hard_limit,
    )
    statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))
    idle_timeout_ms = int(os.getenv("DB_POOL_IDLE_TIMEOUT_MS", "300000"))
    conn_max_age = int(os.getenv("CONN_MAX_AGE", "60"))

    config: dict[str, Any] = {
        "connect_timeout": 10,
        "options": f"-c statement_timeout={statement_timeout_ms}ms",
        # django-postgrespool2 / geventpool
        "POOL_OPTIONS": {
            "POOL_SIZE": min_size,
            "MAX_OVERFLOW": max(0, max_size - min_size),
            "RECYCLE": idle_timeout_ms // 1000,
            "TIMEOUT": 10,
            "PRE_PING": True,
        },
        # psycopg3 built-in pool (future)
        "pool": {
            "min_size": min_size,
            "max_size": max_size,
            "reconnect_timeout": 10,
            "max_idle": idle_timeout_ms / 1000,
        },
        # Expose calculated values for observability
        "_pool_min": min_size,
        "_pool_max": max_size,
        "_conn_max_age": conn_max_age,
        "_statement_timeout_ms": statement_timeout_ms,
    }
    return config


# ---------------------------------------------------------------------------
# Prometheus metrics export
# ---------------------------------------------------------------------------

def emit_pool_metrics() -> None:
    """Export live PostgreSQL connection stats to Prometheus.

    Reads from ``pg_stat_activity`` and updates gauges defined in
    ``soroscan.ingest.metrics``.  Intended to be called periodically by a
    Celery beat task.

    This function is a no-op if the database is not PostgreSQL or if the
    metrics module is unavailable (e.g. in unit tests).
    """
    try:
        from django.db import connection  # noqa: PLC0415

        if connection.vendor != "postgresql":
            return

        with connection.cursor() as cursor:
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
                    ) AS idle_in_transaction
                FROM pg_stat_activity
                """
            )
            row = cursor.fetchone()

        if row is None:
            return

        total, active, idle, wait_queue, idle_in_txn = row

        # Update Prometheus gauges if they exist.
        try:
            from prometheus_client import Gauge, REGISTRY  # noqa: PLC0415
            from soroscan.ingest.metrics import _get_or_create  # noqa: PLC0415

            pg_total = _get_or_create(
                Gauge,
                "soroscan_db_connections_total",
                "Total live PostgreSQL connections for the current database",
            )
            pg_active = _get_or_create(
                Gauge,
                "soroscan_db_connections_active",
                "PostgreSQL connections currently executing queries",
            )
            pg_idle = _get_or_create(
                Gauge,
                "soroscan_db_connections_idle",
                "PostgreSQL connections currently idle",
            )
            pg_wait = _get_or_create(
                Gauge,
                "soroscan_db_connections_wait_queue",
                "PostgreSQL connections waiting on a database wait event",
            )
            pg_idle_txn = _get_or_create(
                Gauge,
                "soroscan_db_connections_idle_in_transaction",
                "PostgreSQL connections in idle-in-transaction state",
            )

            pg_total.set(int(total or 0))
            pg_active.set(int(active or 0))
            pg_idle.set(int(idle or 0))
            pg_wait.set(int(wait_queue or 0))
            pg_idle_txn.set(int(idle_in_txn or 0))

            logger.debug(
                "DB pool metrics: total=%d active=%d idle=%d wait=%d idle_txn=%d",
                total,
                active,
                idle,
                wait_queue,
                idle_in_txn,
            )
        except Exception:  # pragma: no cover
            logger.debug("Could not update Prometheus DB pool gauges.", exc_info=True)

    except Exception:  # pragma: no cover
        logger.warning("emit_pool_metrics: failed to query pg_stat_activity.", exc_info=True)


# ---------------------------------------------------------------------------
# Validated default configuration
# ---------------------------------------------------------------------------

#: Pre-computed settings at module import time.  Import this constant from
#: ``settings.py`` to avoid recomputing limits on every database connection.
DB_POOL_SETTINGS: dict[str, Any] = get_pool_config()
