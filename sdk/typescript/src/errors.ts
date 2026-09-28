/**
 * Typed error hierarchy for the SoroScan TypeScript SDK.
 *
 * All errors extend `SoroScanError`, which extends the native `Error` class.
 * Consumers can catch errors at any level of granularity:
 *
 * @example
 * ```ts
 * try {
 *   const events = await client.getEvents({ contractId });
 * } catch (err) {
 *   if (err instanceof SoroScanRateLimitError) {
 *     console.log(`Retry after ${err.retryAfter}s`);
 *   } else if (err instanceof SoroScanValidationError) {
 *     console.log(`Invalid field: ${err.field}`);
 *   } else if (err instanceof SoroScanAuthenticationError) {
 *     console.log('Authentication failed — check your API key');
 *   } else if (err instanceof SoroScanError) {
 *     console.log(`SDK error ${err.statusCode}: ${err.message}`);
 *   }
 * }
 * ```
 *
 * Error hierarchy:
 * ```
 * Error
 * └── SoroScanError          (base; all SDK errors)
 *     ├── SoroScanApiError           (HTTP error responses)
 *     │   ├── SoroScanAuthenticationError (401)
 *     │   ├── SoroScanAuthorizationError  (403)
 *     │   ├── SoroScanNotFoundError       (404)
 *     │   ├── SoroScanRateLimitError      (429)
 *     │   ├── SoroScanValidationError     (400)
 *     │   └── SoroScanServerError         (5xx)
 *     └── SoroScanNetworkError       (transport-level failures)
 *         ├── SoroScanTimeoutError
 *         └── SoroScanConnectionError
 * ```
 */

// ---------------------------------------------------------------------------
// Base error
// ---------------------------------------------------------------------------

/**
 * Base class for all SoroScan SDK errors.
 *
 * Catching `SoroScanError` covers all SDK-originated failures including
 * API errors and network errors.
 */
export class SoroScanError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SoroScanError";
    // Restore prototype chain after transpilation (needed for `instanceof`)
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// API errors (HTTP response failures)
// ---------------------------------------------------------------------------

/**
 * Raised when the SoroScan API returns an error HTTP response.
 *
 * Subclasses provide more specific error types based on HTTP status code.
 * Catching `SoroScanApiError` covers all non-2xx API responses.
 */
export class SoroScanApiError extends SoroScanError {
  /** HTTP status code returned by the API */
  readonly statusCode: number;
  /** Machine-readable error code from the API (e.g. "not_found", "rate_limit_exceeded") */
  readonly code: string;
  /** Structured error details from the API response body */
  readonly details: Record<string, unknown> | undefined;

  constructor(
    message: string,
    statusCode: number,
    code: string = "unknown_error",
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "SoroScanApiError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when a request fails due to missing or invalid authentication (HTTP 401).
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanAuthenticationError) {
 *   // API key is missing or invalid — prompt for re-authentication
 * }
 * ```
 */
export class SoroScanAuthenticationError extends SoroScanApiError {
  constructor(
    message: string = "Authentication failed — invalid or missing API key",
    code: string = "unauthorized",
    details?: Record<string, unknown>
  ) {
    super(message, 401, code, details);
    this.name = "SoroScanAuthenticationError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when a request is authenticated but forbidden (HTTP 403).
 *
 * The caller's credentials are valid but they do not have permission to
 * perform the requested operation.
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanAuthorizationError) {
 *   // The user is logged in but lacks the required permission
 * }
 * ```
 */
export class SoroScanAuthorizationError extends SoroScanApiError {
  constructor(
    message: string = "Forbidden — insufficient permissions",
    code: string = "forbidden",
    details?: Record<string, unknown>
  ) {
    super(message, 403, code, details);
    this.name = "SoroScanAuthorizationError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when a requested resource cannot be found (HTTP 404).
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanNotFoundError) {
 *   console.log(`Not found: ${err.resourceType} ${err.resourceId}`);
 * }
 * ```
 */
export class SoroScanNotFoundError extends SoroScanApiError {
  /** Type of resource that was not found (e.g. "contract", "webhook") */
  readonly resourceType: string | undefined;
  /** Identifier of the resource that was not found */
  readonly resourceId: string | undefined;

  constructor(
    message: string = "Resource not found",
    code: string = "not_found",
    details?: Record<string, unknown>,
    resourceType?: string,
    resourceId?: string
  ) {
    super(message, 404, code, details);
    this.name = "SoroScanNotFoundError";
    this.resourceType = resourceType;
    this.resourceId = resourceId;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when the API rate limit has been exceeded (HTTP 429).
 *
 * Check `retryAfter` to determine when it is safe to retry the request.
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanRateLimitError) {
 *   const waitSecs = err.retryAfter ?? 60;
 *   await new Promise(r => setTimeout(r, waitSecs * 1000));
 * }
 * ```
 */
export class SoroScanRateLimitError extends SoroScanApiError {
  /** Seconds to wait before retrying (from Retry-After header or API body) */
  readonly retryAfter: number | undefined;
  /** Rate limit ceiling configured for this caller */
  readonly limit: number | undefined;
  /** Remaining calls in the current window */
  readonly remaining: number | undefined;

  constructor(
    message: string = "Rate limit exceeded",
    code: string = "rate_limit_exceeded",
    details?: Record<string, unknown>,
    retryAfter?: number,
    limit?: number,
    remaining?: number
  ) {
    super(message, 429, code, details);
    this.name = "SoroScanRateLimitError";
    this.retryAfter = retryAfter;
    this.limit = limit;
    this.remaining = remaining;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when request validation fails (HTTP 400).
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanValidationError) {
 *   console.log(`Invalid value for field: ${err.field}`);
 *   for (const e of err.errors) console.log(e);
 * }
 * ```
 */
export class SoroScanValidationError extends SoroScanApiError {
  /** Field name that caused the validation failure */
  readonly field: string | undefined;
  /** Value that failed validation */
  readonly value: unknown;
  /** Structured list of validation errors from the API */
  readonly errors: Array<Record<string, unknown>>;

  constructor(
    message: string = "Request validation failed",
    code: string = "validation_error",
    details?: Record<string, unknown>,
    field?: string,
    value?: unknown,
    errors: Array<Record<string, unknown>> = []
  ) {
    super(message, 400, code, details);
    this.name = "SoroScanValidationError";
    this.field = field;
    this.value = value;
    this.errors = errors;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when the API returns a 5xx server error.
 *
 * These errors are generally transient and safe to retry after a delay.
 */
export class SoroScanServerError extends SoroScanApiError {
  constructor(
    message: string,
    statusCode: number,
    code: string = "server_error",
    details?: Record<string, unknown>
  ) {
    super(message, statusCode, code, details);
    this.name = "SoroScanServerError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Network / transport errors
// ---------------------------------------------------------------------------

/**
 * Base class for network and transport-level failures.
 *
 * These errors indicate that the request did not reach the API, or that the
 * TCP connection was disrupted before a response was received.
 */
export class SoroScanNetworkError extends SoroScanError {
  /** URL that was being requested when the error occurred */
  readonly url: string | undefined;

  constructor(message: string, url?: string) {
    super(message);
    this.name = "SoroScanNetworkError";
    this.url = url;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when a request exceeds the configured timeout.
 *
 * @example
 * ```ts
 * if (err instanceof SoroScanTimeoutError) {
 *   console.log(`Timed out after ${err.timeoutMs}ms`);
 * }
 * ```
 */
export class SoroScanTimeoutError extends SoroScanNetworkError {
  /** Timeout in milliseconds that was exceeded */
  readonly timeoutMs: number | undefined;

  constructor(message: string, url?: string, timeoutMs?: number) {
    super(message, url);
    this.name = "SoroScanTimeoutError";
    this.timeoutMs = timeoutMs;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when a connection to the API could not be established.
 *
 * Common causes: incorrect `baseUrl`, network unavailable, DNS failure.
 */
export class SoroScanConnectionError extends SoroScanNetworkError {
  constructor(message: string, url?: string) {
    super(message, url);
    this.name = "SoroScanConnectionError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

// ---------------------------------------------------------------------------
// Internal helper — map an HTTP response to the correct error subclass
// ---------------------------------------------------------------------------

/**
 * Map an HTTP status code and API error body to the appropriate SDK error.
 *
 * Used internally by the client; not intended for direct consumer use.
 *
 * @internal
 */
export function mapApiError(
  statusCode: number,
  code: string,
  message: string,
  details?: Record<string, unknown>
): SoroScanApiError {
  switch (statusCode) {
    case 400:
      return new SoroScanValidationError(
        message,
        code,
        details,
        details?.["field"] as string | undefined,
        details?.["value"],
        (details?.["errors"] as Array<Record<string, unknown>>) ?? []
      );
    case 401:
      return new SoroScanAuthenticationError(message, code, details);
    case 403:
      return new SoroScanAuthorizationError(message, code, details);
    case 404:
      return new SoroScanNotFoundError(
        message,
        code,
        details,
        details?.["resource_type"] as string | undefined,
        details?.["resource_id"] as string | undefined
      );
    case 429:
      return new SoroScanRateLimitError(
        message,
        code,
        details,
        details?.["retry_after"] as number | undefined,
        details?.["limit"] as number | undefined,
        details?.["remaining"] as number | undefined
      );
    default:
      if (statusCode >= 500) {
        return new SoroScanServerError(message, statusCode, code, details);
      }
      return new SoroScanApiError(message, statusCode, code, details);
  }
}
