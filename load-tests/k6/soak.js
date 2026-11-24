/**
 * SoroScan k6 soak & stress load test.
 *
 * Sustained-load and stress-ramp profiles for detecting long-run memory and
 * latency degradation that the smoke and short scenario scripts do not cover.
 *
 * Select a profile with K6_PROFILE:
 *   - soak   (default): constant moderate load for a configurable duration
 *   - stress: ramp VUs up to a high target to find the breaking point
 *
 * The soak profile watches per-iteration latency (`iteration_duration`) and
 * request p95 over a sustained run; a rising trend signals degradation that
 * usually tracks server-side memory/resource leaks (monitor those separately).
 *
 * Refuses production targets unless ALLOW_PRODUCTION_LOAD=true.
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";
import { assertSafeTarget } from "./lib/safety.js";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const TOKEN_USER = __ENV.K6_USERNAME || "";
const TOKEN_PASSWORD = __ENV.K6_PASSWORD || "";
const API_TOKEN = __ENV.K6_API_TOKEN || "";
const PROFILE = (__ENV.K6_PROFILE || "soak").toLowerCase();

// Soak profile: sustained moderate load.
const SOAK_VUS = Number(__ENV.K6_SOAK_VUS || 10);
const SOAK_DURATION = __ENV.K6_SOAK_DURATION || "10m";
const SOAK_RAMP_UP = __ENV.K6_RAMP_UP || "30s";

// Stress profile: ramp to a high target, hold, then ramp down.
const STRESS_MAX_VUS = Number(__ENV.K6_STRESS_VUS || 100);
const STRESS_RAMP_UP = __ENV.K6_RAMP_UP || "1m";
const STRESS_PLATEAU = __ENV.K6_DURATION || "3m";
const STRESS_RAMP_DOWN = __ENV.K6_RAMP_DOWN || "1m";

const scenarios = {};
const thresholds = {};

if (PROFILE === "soak") {
  scenarios.soak = {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: SOAK_RAMP_UP, target: SOAK_VUS },
      { duration: SOAK_DURATION, target: SOAK_VUS },
    ],
    gracefulRampDown: "30s",
    exec: "coreFlow",
  };
  thresholds.http_req_failed = ["rate<0.05"];
  thresholds["http_req_duration{scenario:soak}"] = ["p(95)<2000"];
  thresholds["iteration_duration{scenario:soak}"] = ["p(95)<3000"];
} else if (PROFILE === "stress") {
  scenarios.stress = {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: STRESS_RAMP_UP, target: STRESS_MAX_VUS },
      { duration: STRESS_PLATEAU, target: STRESS_MAX_VUS },
      { duration: STRESS_RAMP_DOWN, target: 0 },
    ],
    gracefulRampDown: "30s",
    exec: "coreFlow",
  };
  thresholds.http_req_failed = ["rate<0.1"];
  thresholds["http_req_duration{scenario:stress}"] = ["p(95)<5000"];
} else {
  throw new Error(`Unknown K6_PROFILE "${PROFILE}". Use "soak" or "stress".`);
}

export const options = { scenarios, thresholds };

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (API_TOKEN) {
    headers.Authorization = `Bearer ${API_TOKEN}`;
  }
  return headers;
}

export function setup() {
  assertSafeTarget(BASE_URL);
  let token = API_TOKEN;
  if (!token && TOKEN_USER && TOKEN_PASSWORD) {
    const res = http.post(
      `${BASE_URL}/api/token/`,
      JSON.stringify({ username: TOKEN_USER, password: TOKEN_PASSWORD }),
      { headers: { "Content-Type": "application/json" } }
    );
    if (res.status === 200) {
      try {
        token = res.json("access") || "";
      } catch (err) {
        token = "";
      }
    }
  }
  return { token };
}

export function coreFlow() {
  group("health and readiness", () => {
    const health = http.get(`${BASE_URL}/api/ingest/health/`, {
      tags: { name: "health" },
    });
    check(health, { "health 200": (r) => r.status === 200 });

    const ready = http.get(`${BASE_URL}/ready/`, {
      tags: { name: "ready" },
      responseCallback: http.expectedStatuses(200, 503),
    });
    check(ready, {
      "readiness reachable": (r) => [200, 503].includes(r.status),
    });
  });

  group("browse contracts", () => {
    const res = http.get(`${BASE_URL}/api/ingest/contracts/`, {
      headers: authHeaders(),
      tags: { name: "contracts-list" },
      responseCallback: http.expectedStatuses(200, 401, 403),
    });
    check(res, {
      "contracts responds": (r) => [200, 401, 403].includes(r.status),
    });
  });

  group("query events", () => {
    const rest = http.get(`${BASE_URL}/api/ingest/events/`, {
      headers: authHeaders(),
      tags: { name: "events-list" },
      responseCallback: http.expectedStatuses(200, 401, 403),
    });
    check(rest, {
      "events responds": (r) => [200, 401, 403].includes(r.status),
    });
  });

  sleep(1);
}

export function handleSummary(data) {
  const reportPath =
    __ENV.K6_REPORT_PATH || `load-tests/results/${PROFILE}-summary.json`;
  return {
    stdout: textSummary(data, { indent: " ", enableColors: true }),
    [reportPath]: JSON.stringify(data, null, 2),
  };
}
