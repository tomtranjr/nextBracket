import { describe, expect, it } from "vitest";

import { ApiError, createApiClient, errorMessage } from "@/lib/api";
import type { ScoreRequest } from "@/lib/types";

interface Call {
  url: string;
  init: RequestInit | undefined;
}

// A stub fetch that records the call and answers with a fixed response.
function stubFetch(response: Response) {
  const calls: Call[] = [];
  const fetchFn: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), init });
    return response;
  };
  return { calls, fetchFn };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const scoreRequest: ScoreRequest = {
  profile: { age: 27, sex: "M" },
  results: { values: { pushup: 45 } },
};

describe("createApiClient", () => {
  it("sends GET /health with no body", async () => {
    const { calls, fetchFn } = stubFetch(json({ status: "ok" }));
    const result = await createApiClient("http://api.test", fetchFn).health();

    expect(result).toEqual({ status: "ok" });
    expect(calls[0].url).toBe("http://api.test/health");
    expect(calls[0].init?.method).toBe("GET");
    expect(calls[0].init?.body).toBeUndefined();
  });

  it("sends GET /versions", async () => {
    const body = { default: "2026-03-01", versions: [] };
    const { calls, fetchFn } = stubFetch(json(body));

    expect(await createApiClient("http://api.test", fetchFn).versions()).toEqual(body);
    expect(calls[0].url).toBe("http://api.test/versions");
  });

  it.each([
    ["score", "/score"],
    ["plan", "/plan"],
    ["standards", "/standards"],
  ] as const)("sends POST %s as JSON", async (name, path) => {
    const { calls, fetchFn } = stubFetch(json({ ok: true }));
    const client = createApiClient("http://api.test", fetchFn);
    const request = { ...scoreRequest, target: 90 };

    // The test only checks the wire format, so one request shape fits all three methods.
    await client[name](request as never);

    expect(calls[0].url).toBe(`http://api.test${path}`);
    expect(calls[0].init?.method).toBe("POST");
    expect(calls[0].init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(String(calls[0].init?.body))).toEqual(request);
  });

  it("returns the parsed body", async () => {
    const report = { total: 80.5, category: "satisfactory" };
    const { fetchFn } = stubFetch(json(report));

    expect(await createApiClient("http://api.test", fetchFn).score(scoreRequest)).toEqual(report);
  });

  it("passes the abort signal to fetch", async () => {
    const { calls, fetchFn } = stubFetch(json({ total: 80 }));
    const controller = new AbortController();
    await createApiClient("http://api.test", fetchFn).score(scoreRequest, controller.signal);

    expect(calls[0].init?.signal).toBe(controller.signal);
  });

  it("rejects with AbortError, not ApiError, when the signal aborts", async () => {
    // Like a real fetch: reject with the signal's reason once it aborts.
    const fetchFn: typeof fetch = (_input, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      });
    const controller = new AbortController();
    const pending = createApiClient("http://api.test", fetchFn)
      .score(scoreRequest, controller.signal)
      .catch((err: unknown) => err);
    controller.abort();

    const error = await pending;
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ name: "AbortError" });
  });

  it("drops trailing slashes from the base URL", async () => {
    const { calls, fetchFn } = stubFetch(json({ status: "ok" }));
    await createApiClient("http://api.test//", fetchFn).health();

    expect(calls[0].url).toBe("http://api.test/health");
  });
});

describe("errors", () => {
  async function failure(response: Response): Promise<ApiError> {
    const { fetchFn } = stubFetch(response);
    const error = await createApiClient("http://api.test", fetchFn)
      .score(scoreRequest)
      .catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ApiError);
    return error as ApiError;
  }

  it("reads a string detail", async () => {
    const error = await failure(json({ detail: "unknown event 'swim'" }, 422));

    expect(error.status).toBe(422);
    expect(error.detail).toBe("unknown event 'swim'");
  });

  it("reads a list of field errors", async () => {
    const error = await failure(
      json(
        {
          detail: [
            { loc: ["body", "profile", "age"], msg: "Input should be at least 17" },
            { loc: ["body"], msg: "Field required" },
          ],
        },
        422,
      ),
    );

    expect(error.detail).toBe("profile.age: Input should be at least 17; Field required");
  });

  it("falls back to the status when the body is not JSON", async () => {
    const error = await failure(new Response("<html>Bad gateway</html>", { status: 502 }));

    expect(error.status).toBe(502);
    expect(error.detail).toBe("HTTP 502");
  });

  it("falls back to the status when the JSON has no detail", async () => {
    const error = await failure(json({ message: "nope" }, 500));

    expect(error.detail).toBe("HTTP 500");
  });
});

describe("errorMessage", () => {
  it("shows the detail of a 422", () => {
    expect(errorMessage(new ApiError(422, "age must be 17 to 70"))).toBe("age must be 17 to 70");
  });

  it("says the service did not answer for any other failure", () => {
    const text = "Cannot reach the scoring service. Try again in a moment.";
    expect(errorMessage(new ApiError(500, "HTTP 500"))).toBe(text);
    expect(errorMessage(new TypeError("Failed to fetch"))).toBe(text);
  });
});
