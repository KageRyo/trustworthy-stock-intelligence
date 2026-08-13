import { z } from "zod";
import {
  apiErrorSchema,
  currentModelSchema,
  predictionBatchSchema,
  predictionJobResponseSchema,
  statusSchema,
  tickerListSchema,
  tickerAnalysisSchema,
  warningHistorySchema,
  watchlistSchema,
  type APIStatus,
  type CurrentModel,
  type PredictionBatch,
  type PredictionJob,
  type TickerList,
  type TickerAnalysis,
  type WarningHistory,
  type Watchlist
} from "./schemas";

const API_BASE_URL = (import.meta.env.VITE_TSI_API_BASE_URL ?? "").replace(/\/$/, "");

type QueryValue = string | number | boolean | undefined;

export class APIClientError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, options: { code: string; status: number }) {
    super(message);
    this.name = "APIClientError";
    this.code = options.code;
    this.status = options.status;
  }
}

function apiUrl(path: string, query?: Record<string, QueryValue>): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  }
  const suffix = searchParams.toString();
  return `${API_BASE_URL}${normalizedPath}${suffix ? `?${suffix}` : ""}`;
}

async function fetchSchema<T>(path: string, schema: z.ZodType<T>, query?: Record<string, QueryValue>) {
  const url = apiUrl(path, query);
  const response = await fetch(url, {
    headers: {
      Accept: "application/json"
    }
  });
  const payload = await readJSONResponse(response, url);

  if (!response.ok) {
    const parsedError = apiErrorSchema.safeParse(payload);
    if (parsedError.success) {
      throw new APIClientError(parsedError.data.error.message, {
        code: parsedError.data.error.code,
        status: response.status
      });
    }
    throw new APIClientError(`API request failed with status ${response.status}`, {
      code: "invalid_error_schema",
      status: response.status
    });
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new APIClientError("API response did not match the expected schema", {
      code: "invalid_response_schema",
      status: response.status
    });
  }
  return parsed.data;
}

async function mutateSchema<T>(
  path: string,
  schema: z.ZodType<T>,
  options: { method: "POST" | "DELETE"; body?: unknown }
) {
  const url = apiUrl(path);
  const response = await fetch(url, {
    method: options.method,
    headers: {
      Accept: "application/json",
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" })
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  const payload = await readJSONResponse(response, url);

  if (!response.ok) {
    const parsedError = apiErrorSchema.safeParse(payload);
    if (parsedError.success) {
      throw new APIClientError(parsedError.data.error.message, {
        code: parsedError.data.error.code,
        status: response.status
      });
    }
    throw new APIClientError(`API request failed with status ${response.status}`, {
      code: "invalid_error_schema",
      status: response.status
    });
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new APIClientError("API response did not match the expected schema", {
      code: "invalid_response_schema",
      status: response.status
    });
  }
  return parsed.data;
}

async function readJSONResponse(response: Response, url: string): Promise<unknown> {
  const body = await response.text();
  if (!body.trim()) {
    throw new APIClientError(`API returned an empty response for ${url}`, {
      code: "empty_response",
      status: response.status
    });
  }

  try {
    return JSON.parse(body) as unknown;
  } catch {
    throw new APIClientError(`API returned non-JSON response for ${url}`, {
      code: "invalid_json_response",
      status: response.status
    });
  }
}

export function fetchStatus(): Promise<APIStatus> {
  return fetchSchema("/api/v1/status", statusSchema);
}

export function fetchCurrentModel(): Promise<CurrentModel> {
  return fetchSchema("/api/v1/models/current", currentModelSchema);
}

export function createPredictionJob(
  ticker: string,
  options: {
    idempotencyKey?: string;
    market?: "auto" | "us" | "twse" | "tpex" | "emerging";
    featureInterval?: "1m" | "5m" | "1d";
    maxAttempts?: number;
  } = {}
): Promise<PredictionJob> {
  return mutateSchema("/api/v1/prediction-jobs", predictionJobResponseSchema, {
    method: "POST",
    body: {
      schema_version: "prediction_job_request.v1",
      ticker: ticker.trim().toUpperCase(),
      ...(options.idempotencyKey === undefined ? {} : { idempotency_key: options.idempotencyKey }),
      market: options.market ?? "auto",
      feature_interval: options.featureInterval ?? "1d",
      ...(options.maxAttempts === undefined ? {} : { max_attempts: options.maxAttempts })
    }
  }).then((response) => response.job);
}

export function fetchPredictionJob(jobId: string): Promise<PredictionJob> {
  return fetchSchema(
    `/api/v1/prediction-jobs/${encodeURIComponent(jobId.trim())}`,
    predictionJobResponseSchema
  ).then((response) => response.job);
}

export function fetchTickerAnalysis(ticker: string): Promise<TickerAnalysis> {
  return fetchSchema(
    `/api/v1/analysis/${encodeURIComponent(ticker.trim().toUpperCase())}`,
    tickerAnalysisSchema
  );
}

export function fetchTickerHistory(ticker: string, limit = 90): Promise<WarningHistory> {
  return fetchSchema(
    `/api/v1/analysis/${encodeURIComponent(ticker.trim().toUpperCase())}/history`,
    warningHistorySchema,
    { limit }
  );
}

export function fetchLatestWarnings(limit = 50): Promise<PredictionBatch> {
  return fetchSchema("/api/v1/warnings/latest", predictionBatchSchema, {
    sort: "calibrated_risk_probability",
    order: "desc",
    limit
  });
}

export function fetchTickers(): Promise<TickerList> {
  return fetchSchema("/api/v1/tickers", tickerListSchema);
}

export function fetchWatchlist(name: string): Promise<Watchlist> {
  return fetchSchema(`/api/v1/watchlists/${encodeURIComponent(name)}`, watchlistSchema);
}

export function addWatchlistTicker(ticker: string, name: string): Promise<Watchlist> {
  return mutateSchema(`/api/v1/watchlists/${encodeURIComponent(name)}/tickers`, watchlistSchema, {
    method: "POST",
    body: {
      schema_version: "watchlist_add.v1",
      ticker: ticker.trim().toUpperCase(),
      market: "auto",
      notes: ""
    }
  });
}

export function removeWatchlistTicker(ticker: string, name: string): Promise<Watchlist> {
  return mutateSchema(
    `/api/v1/watchlists/${encodeURIComponent(name)}/tickers/${encodeURIComponent(
      ticker.trim().toUpperCase()
    )}`,
    watchlistSchema,
    { method: "DELETE" }
  );
}
