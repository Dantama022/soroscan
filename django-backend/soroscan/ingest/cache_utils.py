"""
Redis-backed caching for expensive REST and GraphQL queries (issue #131, #1288).

TTLs
----
- CONTRACTS_LIST_TTL_SECONDS : 30s  — REST GET /contracts  (issue #1288)
- QUERY_CACHE_TTL_SECONDS    : 60s  — GraphQL and other REST queries
- CONTRACT_NAME_CACHE_TTL    : 24h  — contract_id → name lookup
- CONTRACT_OBJ_CACHE_TTL     : 1h   — full TrackedContract objects
- DECODED_PAYLOAD_TTL        : 24h  — decoded event payloads

Cache key prefixes
------------------
All keys use the ``soroscan:`` namespace to avoid collisions.

GraphQL caching
---------------
``graphql_query_cache_key`` builds a key from the operation name, query
fingerprint, variables, and optionally the user identity so that:
  - Anonymous and authenticated responses are never cross-cached.
  - Requests with different variables always use different keys.
  - Cache-Control: no-cache bypasses the cache (handled in ThrottledGraphQLView).

Cache miss/hit tracking
-----------------------
``get_or_set_json`` increments Prometheus counters via
``soroscan.ingest.metrics.cache_hits_total`` / ``cache_misses_total``.
"""
import hashlib
import json
import logging
from functools import wraps
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.cache import cache

# Imported at module level so patch('soroscan.ingest.cache_utils.TrackedContract…') works.
from .models import TrackedContract
from .telemetry import tracer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL helpers
# ---------------------------------------------------------------------------

def query_cache_ttl() -> int:
    """TTL for GraphQL and general REST queries (default 60 s)."""
    return int(getattr(settings, "QUERY_CACHE_TTL_SECONDS", 60))


def contracts_list_cache_ttl() -> int:
    """TTL for the REST GET /contracts list endpoint (default 30 s, issue #1288)."""
    return int(getattr(settings, "CONTRACTS_LIST_CACHE_TTL_SECONDS", 30))


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def stable_cache_key(prefix: str, payload: dict[str, Any]) -> str:
    """Deterministic key from a prefix and sorted JSON payload."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:32]
    return f"soroscan:{prefix}:{digest}"


def graphql_query_cache_key(
    operation_name: str | None,
    query: str,
    variables: dict[str, Any] | None,
    user_id: int | str | None,
) -> str:
    """Return a deterministic Redis key for a GraphQL query result.

    Two requests with different variables, operation names, or authenticated
    users will never share the same key, preventing cross-user data leakage.

    Parameters
    ----------
    operation_name:
        GraphQL operation name from the request body, or ``None``.
    query:
        Full GraphQL query string.
    variables:
        Parsed variables dict, or ``None`` / ``{}``.
    user_id:
        Authenticated user's PK, or ``None`` / ``"anon"`` for anonymous
        requests.  **Never include tokens or passwords.**
    """
    payload = {
        "op": operation_name or "",
        "q": query,
        "vars": variables or {},
        "uid": user_id if user_id is not None else "anon",
    }
    return stable_cache_key("graphql", payload)


# ---------------------------------------------------------------------------
# Core get-or-set helper
# ---------------------------------------------------------------------------

_SENTINEL = object()


def get_or_set_json(key: str, ttl: int, factory: Callable[[], Any]) -> Any:
    """Return cached value or compute and store (including cached ``None``).

    Increments Prometheus cache hit/miss counters.
    """
    from .metrics import cache_hits_total, cache_misses_total  # noqa: PLC0415

    cached = cache.get(key, _SENTINEL)
    if cached is not _SENTINEL:
        try:
            cache_hits_total.labels(cache_type="query").inc()
        except Exception:  # pragma: no cover
            pass
        return cached

    try:
        cache_misses_total.labels(cache_type="query").inc()
    except Exception:  # pragma: no cover
        pass

    value = factory()
    try:
        cache.set(key, value, timeout=ttl)
    except Exception:  # pragma: no cover
        # Redis failure: degrade gracefully — return value but don't cache it.
        logger.warning("Cache set failed for key %s; serving uncached response.", key)
    return value


# ---------------------------------------------------------------------------
# Contract-level cache helpers
# ---------------------------------------------------------------------------

def invalidate_contract_query_cache(contract_id: str) -> None:
    """Best-effort: drop stats cache for a contract (pattern-free delete)."""
    cache.delete(stable_cache_key("contract_stats", {"contract_id": contract_id}))


def contract_cache_key(contract_id: str) -> str:
    """Return the Redis key for a cached TrackedContract object."""
    return f"soroscan:contract:obj:{contract_id}"


# 24-hour TTL for contract-name cache entries (Issue #778)
CONTRACT_NAME_CACHE_TTL = 86_400
# 1-hour TTL for full TrackedContract objects
CONTRACT_OBJ_CACHE_TTL = 3_600


def contract_name_cache_key(contract_id: str) -> str:
    """Return the Redis key for the contract_address → contract_name mapping.

    Used by ``warm_contract_name_cache`` to pre-populate a lightweight lookup
    that does not require loading full TrackedContract instances.

    Key pattern: ``soroscan:contract:name:{contract_id}``
    TTL: 24 hours (see CONTRACT_NAME_CACHE_TTL).
    """
    return f"soroscan:contract:name:{contract_id}"


def get_cached_contract(contract_id: str) -> Any:
    """Get a TrackedContract instance from cache, or load from DB and cache it."""
    with tracer.start_as_current_span(
        "ingest.contract_lookup",
        attributes={"contract_id": contract_id},
    ):
        key = contract_cache_key(contract_id)
        contract = cache.get(key)
        if contract is not None:
            return contract

        try:
            with tracer.start_as_current_span(
                "db.query.contract_lookup",
                attributes={"contract_id": contract_id},
            ):
                contract = TrackedContract.objects.get(contract_id=contract_id)
            try:
                cache.set(key, contract, timeout=CONTRACT_OBJ_CACHE_TTL)
            except Exception:  # pragma: no cover
                logger.warning("Cache set failed for contract %s.", contract_id)
            return contract
        except TrackedContract.DoesNotExist:
            return None


def invalidate_cached_contract(contract_id: str) -> None:
    """Invalidate the cached TrackedContract object."""
    cache.delete(contract_cache_key(contract_id))


# ---------------------------------------------------------------------------
# Event count cache helpers
# ---------------------------------------------------------------------------

def get_event_count(contract_id: str) -> int:
    """Get cached event count for a contract with 5-minute TTL."""
    from .metrics import cache_hits_total, cache_misses_total  # noqa: PLC0415

    key = f"event_count:{contract_id}"
    count = cache.get(key)
    if count is None:
        cache_misses_total.labels(cache_type="event_count").inc()
        from .models import ContractEvent  # noqa: PLC0415
        count = ContractEvent.objects.filter(contract__contract_id=contract_id).count()
        try:
            cache.set(key, count, 300)  # 5 min TTL
        except Exception:  # pragma: no cover
            logger.warning("Cache set failed for event count %s.", contract_id)
    else:
        cache_hits_total.labels(cache_type="event_count").inc()
    return count


def invalidate_event_count_cache(contract_id: str) -> None:
    """Invalidate event count cache for a contract."""
    key = f"event_count:{contract_id}"
    cache.delete(key)


# ---------------------------------------------------------------------------
# Decoded payload cache helpers
# ---------------------------------------------------------------------------

DECODED_PAYLOAD_TTL = 86_400  # 24 hours


def decoded_payload_cache_key(event_id: int) -> str:
    """Return the Redis key for a cached decoded payload."""
    return f"soroscan:decoded:{event_id}"


def get_cached_decoded_payload(event_id: int) -> Any:
    """Return cached decoded payload or _SENTINEL if not cached."""
    return cache.get(decoded_payload_cache_key(event_id), _SENTINEL)


def set_cached_decoded_payload(event_id: int, payload: Any) -> None:
    """Store decoded payload in cache with 24-hour TTL."""
    try:
        cache.set(decoded_payload_cache_key(event_id), payload, timeout=DECODED_PAYLOAD_TTL)
    except Exception:  # pragma: no cover
        logger.warning("Cache set failed for decoded payload event_id=%d.", event_id)


def invalidate_decoded_payload_cache(event_id: int) -> None:
    """Invalidate the decoded payload cache for a specific event."""
    cache.delete(decoded_payload_cache_key(event_id))


# ---------------------------------------------------------------------------
# REST view caching decorator
# ---------------------------------------------------------------------------

def cache_result(ttl: int) -> Callable:
    """Cache successful DRF function-view responses for ``ttl`` seconds.

    Respects cache-busting: if the ``CacheBustingMiddleware`` has set
    ``request._cache_busting = True`` (i.e. the client sent
    ``Cache-Control: no-cache``), the cache is bypassed and the response is
    not stored.
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # Honour cache-busting set by CacheBustingMiddleware.
            if getattr(request, "_cache_busting", False):
                return view_func(request, *args, **kwargs)

            query_items = (
                sorted(request.query_params.items())
                if hasattr(request, "query_params")
                else []
            )
            payload: dict[str, Any] = {
                "path": request.path,
                "query": query_items,
                "kwargs": kwargs,
            }
            if getattr(request, "user", None) and request.user.is_authenticated:
                payload["user_id"] = request.user.id

            key = stable_cache_key(f"rest_view:{view_func.__name__}", payload)

            cached = cache.get(key, _SENTINEL)
            if cached is not _SENTINEL:
                from rest_framework.response import Response  # noqa: PLC0415

                return Response(cached["data"], status=cached["status"])

            response = view_func(request, *args, **kwargs)
            status_code = getattr(response, "status_code", 500)
            if status_code < 400 and hasattr(response, "data"):
                try:
                    cache.set(
                        key,
                        {"status": status_code, "data": response.data},
                        timeout=ttl,
                    )
                except Exception:  # pragma: no cover
                    logger.warning("Cache set failed for view %s.", view_func.__name__)
            return response

        return wrapped

    return decorator


# ---------------------------------------------------------------------------
# Cache statistics helpers (issue #1288)
# ---------------------------------------------------------------------------

def get_cache_redis_info() -> dict[str, Any]:
    """Return Redis INFO statistics useful for cache observability.

    Returns an empty dict if Redis is unavailable or the backend does not
    expose the underlying client (e.g. LocMemCache in tests).
    """
    try:
        # Django's RedisCache wraps a django_redis client.
        client = cache.client.get_client()  # type: ignore[attr-defined]
        info: dict[str, Any] = client.info()
        return {
            "redis_version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "used_memory_peak_human": info.get("used_memory_peak_human"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "evicted_keys": info.get("evicted_keys"),
            "expired_keys": info.get("expired_keys"),
            "total_commands_processed": info.get("total_commands_processed"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }
    except Exception:
        return {}
