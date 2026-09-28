"""
Typed exception hierarchy for the SoroScan Python SDK.

Hierarchy
---------
Exception
└── SoroScanError              Base for all SDK errors
    ├── SoroScanAPIError       HTTP error responses (non-2xx)
    │   ├── SoroScanAuthenticationError  401
    │   ├── SoroScanAuthorizationError   403
    │   ├── SoroScanAuthError            401 or 403 (catch-all for auth failures)
    │   ├── SoroScanNotFoundError        404
    │   ├── SoroScanRateLimitError       429
    │   ├── SoroScanValidationError      400
    │   └── SoroScanServerError         5xx
    └── SoroScanNetworkError   Transport-level failures
        ├── SoroScanTimeoutError
        └── SoroScanConnectionError

Usage examples
--------------
    try:
        events = client.get_events(contract_id=my_contract)
    except SoroScanRateLimitError as e:
        time.sleep(e.retry_after or 60)
    except SoroScanValidationError as e:
        print(f"Invalid field '{e.field}': {e.message}")
    except SoroScanAuthenticationError:
        print("Invalid or missing API key")
    except SoroScanNotFoundError as e:
        print(f"{e.resource_type} '{e.resource_id}' not found")
    except SoroScanServerError:
        print("Backend error, retry later")
    except SoroScanNetworkError as e:
        print(f"Network failure reaching {e.url}")
    except SoroScanError as e:
        print(f"SDK error: {e.message}")
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base error
# ---------------------------------------------------------------------------


class SoroScanError(Exception):
    """Base exception for all SoroScan SDK errors.

    Catching ``SoroScanError`` covers both API-level and network-level failures.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# API-level errors  (HTTP response failures)
# ---------------------------------------------------------------------------


class SoroScanAPIError(SoroScanError):
    """Raised when the API returns an error HTTP response.

    Attributes
    ----------
    message:       Human-readable description of the error.
    status_code:   HTTP status code (e.g. 400, 401, 404, 429, 500).
    code:          Machine-readable error code from the API response body.
    response_data: Full parsed JSON body of the error response.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code or "unknown_error"
        self.response_data = response_data or {}


class SoroScanAuthError(SoroScanAPIError):
    """Raised when authentication or authorisation fails (HTTP 401 or 403).

    This is the backward-compatible catch-all for authentication failures.
    For finer-grained handling, catch ``SoroScanAuthenticationError`` (401)
    or ``SoroScanAuthorizationError`` (403) separately.
    """


class SoroScanAuthenticationError(SoroScanAuthError):
    """Raised when authentication fails because credentials are missing or invalid (HTTP 401).

    Example
    -------
        except SoroScanAuthenticationError:
            # Prompt the user to re-enter their API key.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 401,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, status_code, code, response_data)


class SoroScanAuthorizationError(SoroScanAuthError):
    """Raised when authenticated credentials lack the required permission (HTTP 403).

    The caller is recognised but is forbidden from performing the operation.

    Example
    -------
        except SoroScanAuthorizationError:
            # The API key is valid but does not have this permission.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 403,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, status_code, code, response_data)


class SoroScanNotFoundError(SoroScanAPIError):
    """Raised when a requested resource cannot be found (HTTP 404).

    Attributes
    ----------
    resource_type: Type of resource that was not found (e.g. ``"contract"``).
    resource_id:   Identifier of the resource that was not found.

    Example
    -------
        except SoroScanNotFoundError as e:
            print(f"{e.resource_type} '{e.resource_id}' does not exist")
    """

    def __init__(
        self,
        message: str,
        status_code: int = 404,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(message, status_code, code, response_data)
        self.resource_type = resource_type
        self.resource_id = resource_id


class SoroScanRateLimitError(SoroScanAPIError):
    """Raised when the API rate limit has been exceeded (HTTP 429).

    Attributes
    ----------
    retry_after: Seconds to wait before retrying (from ``Retry-After`` or
                 the API response body), or ``None`` if not provided.
    limit:       Total rate-limit ceiling for the caller.
    remaining:   Calls remaining in the current window.

    Example
    -------
        except SoroScanRateLimitError as e:
            time.sleep(e.retry_after or 60)
            result = client.get_events(contract_id)
    """

    def __init__(
        self,
        message: str,
        status_code: int = 429,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
        retry_after: int | None = None,
        limit: int | None = None,
        remaining: int | None = None,
    ) -> None:
        super().__init__(message, status_code, code, response_data)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining


class SoroScanValidationError(SoroScanAPIError):
    """Raised when request input fails validation (HTTP 400).

    Attributes
    ----------
    field:  Name of the field that failed validation, or ``None``.
    value:  The value that was rejected, or ``None``.
    errors: List of structured validation errors from the API body.

    Example
    -------
        except SoroScanValidationError as e:
            print(f"Validation failed for '{e.field}': {e.message}")
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str | None = None,
        response_data: dict[str, object] | None = None,
        field: str | None = None,
        value: object | None = None,
        errors: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(message, status_code, code, response_data)
        self.field = field
        self.value = value
        self.errors = errors or []


class SoroScanServerError(SoroScanAPIError):
    """Raised when the API returns a 5xx server error.

    These errors are generally transient and safe to retry after a delay.
    """


# ---------------------------------------------------------------------------
# Network / transport errors
# ---------------------------------------------------------------------------


class SoroScanNetworkError(SoroScanError):
    """Raised when a network error prevents the request from completing.

    Attributes
    ----------
    url:     URL that was being requested, or ``None``.
    timeout: Timeout value in seconds (if applicable), or ``None``.
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.timeout = timeout


class SoroScanTimeoutError(SoroScanNetworkError):
    """Raised when a request exceeds the configured timeout.

    Example
    -------
        except SoroScanTimeoutError as e:
            print(f"Timed out after {e.timeout}s reaching {e.url}")
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(message, url, timeout)


class SoroScanConnectionError(SoroScanNetworkError):
    """Raised when a TCP connection to the API cannot be established.

    Common causes: incorrect ``base_url``, DNS failure, network unreachable.
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
    ) -> None:
        super().__init__(message, url, None)
