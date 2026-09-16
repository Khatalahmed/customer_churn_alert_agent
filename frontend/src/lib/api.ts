/**
 * The only place that talks to the backend.
 *
 * Every call runs on the server (React Server Components), so the API's
 * address never reaches the browser and no credential can leak into client
 * code. The browser talks to this Next app; this app talks to FastAPI.
 */
import "server-only";

import type {
  CustomerSearch,
  CustomerView,
  Economics,
  Evaluations,
  Health,
  Investigation,
  Investigations,
  Outcomes,
  Overview,
  Reliability,
  Timeline,
  Explanation,
  Worklist,
} from "@/types/api";

const BASE = process.env.CHURN_API_URL ?? "http://127.0.0.1:8000";

/** Raised when the service is unreachable or answers with an error. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = {
  /** Seconds to cache. Scores change once per analysis run, not per request. */
  revalidate?: number;
  /** Treat 404 as "no such thing" rather than an error. */
  allow404?: boolean;
};

async function get<T>(path: string, options: Options = {}): Promise<T> {
  const { revalidate = 30, allow404 = false } = options;
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { next: { revalidate } });
  } catch {
    throw new ApiError(
      `Cannot reach the churn service at ${BASE}. Start it with: uv run uvicorn churn.api:app`,
      503,
      path,
    );
  }
  if (response.status === 404 && allow404) {
    throw new ApiError("not found", 404, path);
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiError(detail.slice(0, 300) || response.statusText, response.status, path);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => get<Health>("/health", { revalidate: 10 }),
  overview: (topN = 15) => get<Overview>(`/overview?top_n=${topN}`),
  worklist: (topN = 15) => get<Worklist>(`/worklist?top_n=${topN}`),
  customers: (query = "", limit = 50, offset = 0) =>
    get<CustomerSearch>(
      `/customers?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`,
    ),
  customer: (id: number) => get<CustomerView>(`/customers/${id}`, { allow404: true }),
  timeline: (id: number) => get<Timeline>(`/customers/${id}/timeline`, { allow404: true }),
  explanation: (id: number) =>
    get<Explanation>(`/customers/${id}/explanation`, { allow404: true, revalidate: 300 }),
  investigations: () => get<Investigations>("/investigations"),
  investigation: (id: number) => get<Investigation>(`/investigations/${id}`),
  evaluations: () => get<Evaluations>("/evaluations", { revalidate: 300 }),
  reliability: () => get<Reliability>("/reliability", { revalidate: 120 }),
  outcomes: () => get<Outcomes>("/outcomes", { revalidate: 300 }),
  economics: () => get<Economics>("/economics", { revalidate: 300 }),
};

/**
 * Fetch without letting one dead panel take down a page.
 *
 * A dashboard that 500s because the agent has not run yet is worse than one
 * that says "the agent has not run yet" in the panel that needed it.
 */
export async function attempt<T>(promise: Promise<T>): Promise<T | { error: string }> {
  try {
    return await promise;
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Unknown error" };
  }
}

export function isError<T>(value: T | { error: string }): value is { error: string } {
  return typeof value === "object" && value !== null && "error" in value;
}
