import type { ExplainResponse, HazardReport, Query } from "./types";

/** An API error with a message that is safe and useful to show to the user. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter?: number,
  ) {
    super(message);
  }
}

async function post<T>(path: string, body: Query, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Couldn't reach the server. Check your connection and try again.", 0);
  }
  if (res.ok) return (await res.json()) as T;

  const data = await res.json().catch(() => ({}));
  const retryAfter = Number(res.headers.get("retry-after")) || undefined;
  if (res.status === 422) {
    throw new ApiError("Please describe the product in 10 to 1,000 characters.", 422);
  }
  const detail = typeof data.detail === "string" ? data.detail : "Something went wrong.";
  throw new ApiError(detail, res.status, retryAfter);
}

export const analyze = (q: Query, signal?: AbortSignal) =>
  post<HazardReport>("/api/analyze", q, signal);

export const explain = (q: Query, signal?: AbortSignal) =>
  post<ExplainResponse>("/api/explain", q, signal);
