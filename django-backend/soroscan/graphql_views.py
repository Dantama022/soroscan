"""
Custom GraphQL views with rate limiting, introspection control, and query caching.

Caching strategy (issue #1288)
-------------------------------
- Only GET-equivalent queries are cached (POST with a read-only query body).
- Mutations, subscriptions, and introspection are **never** cached.
- Cache-busting: if the request contains ``Cache-Control: no-cache``, the
  cache is bypassed and the fresh response is **not** stored.
- Per-user isolation: the cache key includes the authenticated user ID so
  different users can never receive each other's data.
- TTL: ``QUERY_CACHE_TTL_SECONDS`` (default 60 s).

The ``X-Cache`` response header reports ``HIT`` or ``MISS`` for debugging.
"""
import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from graphql.error import GraphQLError
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from strawberry.django.views import GraphQLView

from soroscan.graphql_complexity import calculate_complexity, complexity_error_message
from soroscan.throttles import IngestRateThrottle

logger = logging.getLogger(__name__)

_INTROSPECTION_FIELDS = {"__schema", "__type", "__typename"}

# Operations that should never be cached (mutations / subscriptions / special)
_NEVER_CACHE_KEYWORDS = {"mutation", "subscription"}


def _parse_request_body(body: bytes) -> dict:
    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def _is_introspection_query(body: bytes) -> bool:
    """Return True if the request body contains a GraphQL introspection query."""
    query = _parse_request_body(body).get("query", "")
    return any(field in query for field in _INTROSPECTION_FIELDS)


def _is_mutation_or_subscription(query: str) -> bool:
    """Return True if *query* is a mutation or subscription (never cached)."""
    normalized = query.strip().lower()
    return any(normalized.startswith(kw) for kw in _NEVER_CACHE_KEYWORDS)


def _evaluate_query_complexity(body: bytes):
    """
    Return a ComplexityResult for POST bodies with a query, or None otherwise.

    Parse failures are returned as a JsonResponse for the caller to return.
    """
    query = _parse_request_body(body).get("query", "")
    if not query:
        return None

    max_allowed = int(getattr(settings, "GRAPHQL_MAX_COMPLEXITY", 1000))
    try:
        return calculate_complexity(query, max_allowed=max_allowed)
    except GraphQLError as exc:
        return JsonResponse({"errors": [{"message": str(exc)}]}, status=400)


def _graphql_cache_key(query: str, variables: dict, user_id: object) -> str:
    """Build a deterministic Redis key for a GraphQL query result.

    The key incorporates:
    - Normalised query string (whitespace-collapsed SHA-256)
    - Sorted variables JSON
    - User identity (PK or "anon") for per-user isolation
    """
    variables_blob = json.dumps(variables or {}, sort_keys=True, default=str)
    raw = f"{query}|{variables_blob}|{user_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"soroscan:graphql:{digest}"


class ThrottledGraphQLView(GraphQLView):
    """
    GraphQL view with rate limiting, introspection blocking, and query caching.

    Caching behaviour
    -----------------
    - Only read-only (query) operations are cached.
    - Cache-Control: no-cache bypasses the cache.
    - Authenticated and anonymous results are isolated by user ID.
    - Mutations, subscriptions, and introspection are never cached.
    - Successful cached responses carry ``X-Cache: HIT``.

    Rate limiting
    -------------
    Set GRAPHQL_INTROSPECTION_ENABLED=False (default in production) to reject
    introspection queries with a 403 and a clear error message.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anon_throttle = AnonRateThrottle()
        self.user_throttle = UserRateThrottle()
        self.ingest_throttle = IngestRateThrottle()

    def get_throttles(self, request):
        """Return list of throttle instances to check."""
        return [self.anon_throttle, self.user_throttle]

    def check_throttles(self, request):
        """Check if request should be throttled."""
        for throttle in self.get_throttles(request):
            if not throttle.allow_request(request, self):
                self.throttle_failure()

    def throttle_failure(self):
        """Handle throttle failure — raise 429."""
        from rest_framework.exceptions import Throttled

        raise Throttled(detail="Rate limit exceeded. Please try again later.")

    def _is_cache_bust(self, request) -> bool:
        """Return True if the client has requested a fresh response."""
        cc = request.META.get("HTTP_CACHE_CONTROL", "")
        return "no-cache" in cc or "no-store" in cc

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add throttling, introspection checks, and caching."""
        self.check_throttles(request)

        complexity_result = None
        parsed_body: dict = {}
        cache_enabled = getattr(settings, "GRAPHQL_CACHE_ENABLED", True)

        if request.method == "POST":
            body = request.body
            parsed_body = _parse_request_body(body)
            query_str: str = parsed_body.get("query", "")

            # ── Complexity guard ──────────────────────────────────────────────
            complexity_eval = _evaluate_query_complexity(body)
            if isinstance(complexity_eval, JsonResponse):
                return complexity_eval
            complexity_result = complexity_eval

            # ── Introspection guard ───────────────────────────────────────────
            introspection_enabled = getattr(settings, "GRAPHQL_INTROSPECTION_ENABLED", True)
            if not introspection_enabled and _is_introspection_query(body):
                return JsonResponse(
                    {
                        "errors": [
                            {
                                "message": (
                                    "GraphQL introspection is disabled in production. "
                                    "Set GRAPHQL_INTROSPECTION_ENABLED=True to enable it."
                                )
                            }
                        ]
                    },
                    status=403,
                )

            if complexity_result is not None and complexity_result.exceeded:
                return JsonResponse(
                    {
                        "errors": [
                            {"message": complexity_error_message(complexity_result)}
                        ],
                        "extensions": {
                            "complexity": {
                                "score": complexity_result.score,
                                "maxAllowed": complexity_result.max_allowed,
                            }
                        },
                    },
                    status=400,
                )

            # ── Query result caching ─────────────────────────────────────────
            cacheable = (
                cache_enabled
                and bool(query_str)
                and not _is_mutation_or_subscription(query_str)
                and not _is_introspection_query(body)
                and not self._is_cache_bust(request)
            )
            if cacheable:
                user_id = (
                    request.user.pk
                    if hasattr(request, "user") and request.user.is_authenticated
                    else "anon"
                )
                variables = parsed_body.get("variables") or {}
                cache_key = _graphql_cache_key(query_str, variables, user_id)
                ttl = int(getattr(settings, "QUERY_CACHE_TTL_SECONDS", 60))

                cached_payload = cache.get(cache_key)
                if cached_payload is not None:
                    from soroscan.ingest.metrics import cache_hits_total  # noqa: PLC0415
                    try:
                        cache_hits_total.labels(cache_type="graphql").inc()
                    except Exception:
                        pass
                    response = JsonResponse(cached_payload, safe=False)
                    response["X-Cache"] = "HIT"
                    if complexity_result is not None:
                        response["X-GraphQL-Complexity"] = str(complexity_result.score)
                        response["X-GraphQL-Complexity-Limit"] = str(complexity_result.max_allowed)
                    return response

                # Cache miss — execute and store result
                response = super().dispatch(request, *args, **kwargs)
                try:
                    from soroscan.ingest.metrics import cache_misses_total  # noqa: PLC0415
                    cache_misses_total.labels(cache_type="graphql").inc()
                except Exception:
                    pass

                if getattr(response, "status_code", 500) == 200 and hasattr(response, "content"):
                    try:
                        payload = json.loads(response.content)
                        # Only cache responses without errors
                        if not payload.get("errors"):
                            cache.set(cache_key, payload, timeout=ttl)
                    except Exception:
                        logger.debug("GraphQL response not JSON-serialisable; skipping cache.")

                response["X-Cache"] = "MISS"
                if complexity_result is not None and hasattr(response, "__setitem__"):
                    response["X-GraphQL-Complexity"] = str(complexity_result.score)
                    response["X-GraphQL-Complexity-Limit"] = str(complexity_result.max_allowed)
                return response

        response = super().dispatch(request, *args, **kwargs)

        if complexity_result is not None and hasattr(response, "__setitem__"):
            response["X-GraphQL-Complexity"] = str(complexity_result.score)
            response["X-GraphQL-Complexity-Limit"] = str(complexity_result.max_allowed)

        return response
