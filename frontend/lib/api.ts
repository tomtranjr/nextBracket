import type {
  PlanRequest,
  PlanResult,
  ScoreReport,
  ScoreRequest,
  StandardsRequest,
  StandardsTable,
  VersionsResponse,
} from "./types";

// Only `import type` above: it is erased at run time, so a plain Node script can load this file.

// 8000 is the host port in docker-compose.yml and the README examples.
const DEFAULT_BASE_URL = "http://localhost:8000";

/** The API answered with a non-2xx status. `detail` is a message a person can read. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Text for a failed call. A 422 detail is written for a person. Anything else means no answer. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError && error.status === 422
    ? error.detail
    : "Cannot reach the scoring service. Try again in a moment.";
}

interface FieldError {
  loc?: unknown[];
  msg?: string;
}

// FastAPI sends `detail` as a string for our own 422s, and as a list of field errors when
// Pydantic rejects the body. Anything else (a proxy error page) falls back to the status.
function readDetail(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const lines = detail.map((item: FieldError) => {
      // loc starts with "body", which tells a person nothing.
      const path = (item.loc ?? []).filter((part) => part !== "body").join(".");
      return path ? `${path}: ${item.msg ?? "invalid"}` : (item.msg ?? "invalid");
    });
    if (lines.length > 0) return lines.join("; ");
  }
  return fallback;
}

/**
 * Build a client for the Next Bracket API. `fetchFn` is injectable so tests need no network.
 * The default wraps `fetch` in an arrow: a bare `fetch` stored and called later can fail
 * with "Illegal invocation" in some browsers.
 */
export function createApiClient(
  baseUrl: string,
  fetchFn: typeof fetch = (input, init) => fetch(input, init),
) {
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    // An aborted call rejects with the browser's own `AbortError`, not an `ApiError`.
    const response = await fetchFn(`${root}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      const fallback = `HTTP ${response.status}`;
      let detail = fallback;
      try {
        detail = readDetail(await response.json(), fallback);
      } catch {
        // The body was not JSON. Keep the status text.
      }
      throw new ApiError(response.status, detail);
    }
    return (await response.json()) as T;
  }

  return {
    health: () => request<{ status: string }>("GET", "/health"),
    versions: () => request<VersionsResponse>("GET", "/versions"),
    // `signal` lets the live form cancel a request that a newer keystroke has replaced.
    score: (body: ScoreRequest, signal?: AbortSignal) =>
      request<ScoreReport>("POST", "/score", body, signal),
    plan: (body: PlanRequest) => request<PlanResult>("POST", "/plan", body),
    standards: (body: StandardsRequest) => request<StandardsTable>("POST", "/standards", body),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

// Next replaces `process.env.NEXT_PUBLIC_*` with its value at build time, so this name must stay
// spelled out. The value is public, so it never holds a secret.
export const api = createApiClient(process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_BASE_URL);
