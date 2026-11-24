"""Low-cardinality HTTP error metrics for SLA alerting."""

from __future__ import annotations

from prometheus_client import Counter
from django.utils.deprecation import MiddlewareMixin

http_responses_total = Counter(
    "soroscan_http_responses_total",
    "HTTP responses used to calculate service error rates",
    ["service", "status_class", "view", "error_type"],
)


def check_celery_workers(timeout: float) -> dict:
    """Ping Celery workers and summarize their responsiveness.

    Returns a dict with:

    * ``status`` - ``"healthy"`` when at least one worker answered, else
      ``"unhealthy"``.
    * ``workers`` - the mapping Celery returns (worker name -> ping payload)
      when healthy, otherwise an empty dict.
    * ``error`` - a short, fixed reason when unhealthy, otherwise absent.

    The Celery app is imported lazily so importing this module does not
    require a broker connection. A Celery ``TimeoutError`` is reported as
    ``worker ping timeout``; any other inspection failure is collapsed to a
    generic ``worker inspection failed``. Leaking the raw exception text to an
    unauthenticated health endpoint can disclose broker hostnames and internal
    paths, so it is never forwarded.
    """
    from celery.exceptions import TimeoutError as CeleryTimeoutError

    from soroscan.celery import app

    try:
        worker_status = app.control.inspect(timeout=timeout).ping()
    except CeleryTimeoutError:
        return {
            "status": "unhealthy",
            "workers": {},
            "error": "worker ping timeout",
        }
    except Exception:
        return {
            "status": "unhealthy",
            "workers": {},
            "error": "worker inspection failed",
        }

    if not worker_status:
        return {
            "status": "unhealthy",
            "workers": {},
            "error": "no worker responded",
        }

    return {"status": "healthy", "workers": worker_status}


class ErrorRateMetricsMiddleware(MiddlewareMixin):
    """Count responses with service and bounded root-cause labels."""

    async def __call__(self, request):
        response = await self.get_response(request)
        status_code = response.status_code
        match = getattr(request, "resolver_match", None)
        view = (match.view_name if match else None) or "unresolved"
        error_type = ""
        if status_code >= 400:
            data = getattr(response, "data", None)
            if isinstance(data, dict):
                error_type = str(data.get("code") or data.get("detail") or "")
            if not error_type:
                error_type = f"http_{status_code}"
            error_type = error_type[:80]
        http_responses_total.labels(
            service="soroscan-backend",
            status_class=f"{status_code // 100}xx",
            view=view,
            error_type=error_type,
        ).inc()
        return response
