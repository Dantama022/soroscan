"""
Celery configuration for SoroScan project.
"""

import os
import time

from celery import Celery, Task
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    worker_ready,
    worker_process_shutdown,
    worker_shutdown,
    worker_shutting_down,
)
import logging

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "soroscan.settings")


class ContextPropagatingTask(Task):
    """Celery Task base class that propagates the current request_id and traceparent into
    task headers so that Celery worker logs share the same correlation ID
    as the HTTP request that dispatched the task.
    """

    REQUEST_ID_HEADER = "X-Request-ID"
    TRACEPARENT_HEADER = "traceparent"

    def apply_async(self, *args, **kwargs):
        headers = kwargs.setdefault("headers", {})
        from soroscan.log_context import log_context_var

        ctx = log_context_var.get()
        request_id = ctx.get("request_id", "")
        if request_id and self.REQUEST_ID_HEADER not in headers:
            headers[self.REQUEST_ID_HEADER] = request_id
            
        traceparent = ctx.get("traceparent", "")
        if traceparent and self.TRACEPARENT_HEADER not in headers:
            headers[self.TRACEPARENT_HEADER] = traceparent
            
        return super().apply_async(*args, **kwargs)


app = Celery("soroscan")
app.Task = ContextPropagatingTask
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
_task_started_at: dict[str, float] = {}
_metrics_http_server = None


@worker_ready.connect
def start_prometheus_metrics_server(**kwargs):
    """Expose metrics collected from Celery's prefork worker processes."""
    global _metrics_http_server
    if _metrics_http_server is not None or not os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        return

    from prometheus_client import CollectorRegistry, multiprocess, start_http_server

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    _metrics_http_server, _ = start_http_server(
        int(os.getenv("PROMETHEUS_METRICS_PORT", "9100")),
        addr="0.0.0.0",
        registry=registry,
    )


@worker_process_shutdown.connect
def mark_prometheus_worker_process_dead(pid=None, **kwargs):
    """Remove dead child-process gauges when Celery recycles a worker."""
    if pid is None or not os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        return

    from prometheus_client import multiprocess

    multiprocess.mark_process_dead(pid)


@task_prerun.connect
def set_celery_task_context(sender, task_id, **kwargs):
    """Set task_id in log context so Celery logs include it (no PII)."""
    from soroscan.log_context import set_request_id, set_task_id, log_context_var

    set_task_id(task_id or "")

    request = kwargs.get("request")
    if request is not None:
        request_id = ""
        traceparent = ""
        headers = getattr(request, "headers", None)
        
        if isinstance(headers, dict):
            request_id = headers.get("X-Request-ID", "")
            traceparent = headers.get("traceparent", "")
            
        if not request_id or not traceparent:
            delivery_info = getattr(request, "delivery_info", None)
            if isinstance(delivery_info, dict):
                request_id = request_id or delivery_info.get("X-Request-ID", "")
                traceparent = traceparent or delivery_info.get("traceparent", "")
                
        if request_id:
            set_request_id(request_id)
            
        if traceparent:
            ctx = log_context_var.get()
            ctx["traceparent"] = traceparent

    from soroscan.ingest.metrics import celery_tasks_active

    task_name = getattr(sender, "name", "unknown")
    _task_started_at[task_id] = time.monotonic()
    celery_tasks_active.labels(task_name=task_name).inc()


@task_postrun.connect
def record_celery_task_completion(sender, task_id, state, **kwargs):
    """Record task throughput, active count, and duration."""
    from soroscan.ingest.metrics import (
        celery_task_duration_seconds,
        celery_tasks_active,
        celery_tasks_total,
    )

    task_name = getattr(sender, "name", "unknown")
    celery_tasks_active.labels(task_name=task_name).dec()
    if str(state).upper() != "FAILURE":
        celery_tasks_total.labels(
            task_name=task_name, status=str(state).lower(), error_type=""
        ).inc()
    started = _task_started_at.pop(task_id, None)
    if started is not None:
        celery_task_duration_seconds.labels(task_name=task_name).observe(
            time.monotonic() - started
        )


@task_failure.connect
def record_celery_task_failure(sender, exception, **kwargs):
    """Record failure causes for alert and dashboard breakdowns."""
    from soroscan.ingest.metrics import celery_tasks_total

    celery_tasks_total.labels(
        task_name=getattr(sender, "name", "unknown"),
        status="failure",
        error_type=type(exception).__name__,
    ).inc()


@task_retry.connect
def record_celery_task_retry(sender, request, reason, einfo, **kwargs):
    """Log retry details."""
    logger.info(
        "Celery task retrying",
        extra={
            "task_name": getattr(sender, "name", "unknown"),
            "task_id": request.id,
            "retry_attempt": request.retries,
            "max_retries": getattr(sender, "max_retries", None),
            "exception_type": type(reason).__name__,
            "exception_message": str(reason),
            "next_retry_timestamp": str(request.eta) if request.eta else None,
        }
    )


@worker_shutting_down.connect
def _celery_worker_shutting_down(sender, sig=None, how=None, exitcode=None, **kwargs):
    from soroscan.shutdown import on_celery_worker_shutting_down

    on_celery_worker_shutting_down(sig=sig, how=how, exitcode=exitcode, **kwargs)


@worker_shutdown.connect
def _celery_worker_shutdown(sender, **kwargs):
    from soroscan.shutdown import on_celery_worker_shutdown

    on_celery_worker_shutdown(**kwargs)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


@app.task(name="soroscan.celery.chaos_probe")
def chaos_probe():
    """Return a result so chaos tests can verify that a worker processed a task."""
    return "ok"