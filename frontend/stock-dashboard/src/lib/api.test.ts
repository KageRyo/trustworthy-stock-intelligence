import { afterEach, describe, expect, it, vi } from "vitest";
import {
  APIClientError,
  addWatchlistTicker,
  createPredictionJob,
  fetchPredictionJob,
  fetchProviderHealth,
  fetchStatus,
  fetchTickerAnalysis,
  fetchTickerHistory,
  fetchTickerTransitions,
  fetchTickers,
  fetchWatchlist,
  removeWatchlistTicker
} from "./api";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json"
    }
  });
}

function statusPayload() {
  return {
    warnings_path: "postgres",
    warnings_loaded: true,
    schema_version: "v1",
    run_id: "fixture_run",
    data_as_of: "2026-06-19",
    generated_at: "2026-06-19T00:00:00Z",
    record_count: 2,
    last_loaded_at: "2026-06-19T00:01:00Z",
    file_modified_at: "2026-06-19T00:00:30Z"
  };
}

function analysisPayload(ticker = "2330") {
  return {
    schema_version: "analysis.v1",
    ticker,
    date: "2026-06-19",
    run_id: "fixture_run",
    data_as_of: "2026-06-19",
    generated_at: "2026-06-19T00:00:00Z",
    warning: {
      level: "watch",
      risk_probability: 0.31,
      calibrated_risk_probability: 0.22,
      alert_threshold: 0.3,
      watch_threshold: 0.15,
      summary: "Moderate or elevated drawdown-risk signal that should remain on watch."
    },
    trust: {
      trust_score: 0.18,
      uncertainty_score: 0.25,
      calibration_method: "platt",
      trust_status: "limited_trust",
      uncertainty_status: "acceptable_uncertainty",
      summary: "Trust score is below the configured alert threshold for this batch."
    },
    model: {
      name: "temporal_transformer",
      model_bundle: "fixture_bundle"
    },
    data_freshness: {
      data_as_of: "2026-06-19",
      generated_at: "2026-06-19T00:00:00Z",
      last_loaded_at: "2026-06-19T00:01:00Z",
      file_modified_at: "2026-06-19T00:00:30Z",
      record_count: 2,
      freshness: {
        schema_version: "freshness.v1",
        market: "taiwan",
        interval: "1d",
        data_as_of: "2026-06-19",
        evaluated_at: "2026-06-19T00:01:00Z",
        age_seconds: 60,
        fresh_within_seconds: 129600,
        stale_within_seconds: 432000,
        state: "fresh",
        action: "allow",
        reason_code: "freshness_fresh",
        message: "The prediction cutoff is within the configured freshness window."
      }
    },
    calibration_drift: {
      status: "stable",
      method: "calibration_drift_gate_v1",
      event_rate_delta: 0.02,
      ece_delta: 0.01,
      brier_delta: 0.01,
      signals: [],
      degraded: false,
      abstain: false,
      trust_multiplier: 1,
      calibration_rows: 63,
      recent_rows: 21,
      note: "Compared a fitted calibration reference window with later labeled rows."
    },
    reasons: [
      {
        code: "probability_above_watch_threshold",
        severity: "watch",
        title: "Risk probability above watch threshold",
        detail: "The calibrated risk probability is at or above the configured watch threshold."
      }
    ],
    feature_attributions: [
      {
        feature: "return_1d",
        value: -0.02,
        contribution: 0.31,
        direction: "positive",
        method: "standardized_logit_v1"
      }
    ],
    limitations: ["This is a drawdown-risk warning signal, not investment advice."]
  };
}

function historyPayload(ticker = "2330") {
  return {
    schema_version: "warning_history.v1",
    ticker,
    record_count: 1,
    records: [
      {
        run_id: "fixture_run",
        data_as_of: "2026-06-19",
        generated_at: "2026-06-19T00:00:00Z",
        date: "2026-06-19",
        ticker,
        model: "temporal_transformer",
        model_bundle: "fixture_bundle",
        risk_probability: 0.31,
        calibrated_risk_probability: 0.22,
        calibration_method: "platt",
        uncertainty_score: 0.25,
        trust_score: 0.18,
        alert_threshold: 0.3,
        watch_threshold: 0.15,
        warning_level: "watch",
        reason_codes: ["warning_level_watch"]
      }
    ]
  };
}

function tickerListPayload() {
  return {
    schema_version: "ticker_list.v1",
    run_id: "fixture_run",
    data_as_of: "2026-06-19",
    generated_at: "2026-06-19T00:00:00Z",
    record_count: 2,
    tickers: [
      {
        ticker: "2330",
        market: "taiwan",
        date: "2026-06-19",
        warning_level: "watch",
        calibrated_risk_probability: 0.22,
        trust_score: 0.18
      },
      {
        ticker: "NVDA",
        market: "us",
        date: "2026-06-19",
        warning_level: "alert",
        calibrated_risk_probability: 0.31,
        trust_score: 0.28
      }
    ]
  };
}

function watchlistPayload() {
  return {
    schema_version: "watchlist.v1",
    name: "session-test",
    record_count: 1,
    updated_at: "2026-06-19T00:00:00Z",
    tickers: [
      {
        ticker: "2330",
        query_symbol: "2330.TW",
        market: "twse",
        added_at: "2026-06-19T00:00:00Z",
        notes: "",
        has_latest_warning: true,
        latest_warning: {
          date: "2026-06-19",
          warning_level: "watch",
          calibrated_risk_probability: 0.22,
          trust_score: 0.18
        }
      }
    ]
  };
}

function predictionJobPayload(status: "queued" | "completed" = "queued") {
  return {
    schema_version: "prediction_job.v1",
    job: {
      schema_version: "prediction_job.v1",
      id: "job-1",
      idempotency_key: "request-1",
      ticker: "NVDA",
      market: "auto",
      feature_interval: "1d",
      status,
      attempt_count: status === "completed" ? 1 : 0,
      max_attempts: 3,
      available_at: "2026-08-13T02:00:00Z",
      enqueued_at: "2026-08-13T02:00:00Z",
      ...(status === "completed"
        ? {
            completed_at: "2026-08-13T02:01:00Z",
            prediction_batch_id: "batch-1",
            result_run_id: "request-1"
          }
        : {}),
      request_payload: {},
      created_at: "2026-08-13T02:00:00Z",
      updated_at: "2026-08-13T02:00:00Z"
    }
  };
}

function providerHealthPayload() {
  return {
    schema_version: "provider_health.v1",
    generated_at: "2026-08-13T02:00:00Z",
    record_count: 1,
    records: [
      {
        schema_version: "provider_health.v1",
        provider: "twse",
        market: "taiwan",
        ticker: "2330",
        query_symbol: "2330.TW",
        status: "healthy",
        coverage: "available",
        attempt_count: 2,
        success_count: 2,
        failure_count: 0,
        consecutive_failures: 0,
        last_success_at: "2026-08-13T02:00:00Z",
        last_latency_ms: 120,
        observed_at: "2026-08-13T02:00:00Z"
      }
    ]
  };
}

function warningTransitionsPayload() {
  return {
    schema_version: "warning_transition.v1",
    ticker: "NVDA",
    record_count: 1,
    transitions: [
      {
        schema_version: "warning_transition.v1",
        id: "transition-1",
        ticker: "NVDA",
        transition_type: "new_alert",
        current_warning_level: "alert",
        current_run_id: "run-2",
        current_batch_id: "batch-2",
        detected_at: "2026-08-13T02:00:00Z",
        deduplication_key: "NVDA:run-2:new_alert"
      }
    ]
  };
}

afterEach(() => {
  fetchMock.mockReset();
});

describe("typed API client", () => {
  it("parses status responses with the status schema", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(statusPayload()));

    const status = await fetchStatus();

    expect(status.record_count).toBe(2);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/status", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("creates and reads typed prediction jobs", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(predictionJobPayload()));

    const queued = await createPredictionJob(" nvda ", { idempotencyKey: "request-1" });

    expect(queued.status).toBe("queued");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/prediction-jobs", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        schema_version: "prediction_job_request.v1",
        ticker: "NVDA",
        idempotency_key: "request-1",
        market: "auto",
        feature_interval: "1d"
      })
    });

    fetchMock.mockResolvedValueOnce(jsonResponse(predictionJobPayload("completed")));
    const completed = await fetchPredictionJob("job-1");

    expect(completed.status).toBe("completed");
    expect(completed.prediction_batch_id).toBe("batch-1");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/prediction-jobs/job-1", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("supports numeric Taiwan stock codes in analysis URLs", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(analysisPayload("2330")));

    const analysis = await fetchTickerAnalysis("2330");

    expect(analysis.ticker).toBe("2330");
    expect(analysis.feature_attributions?.[0].feature).toBe("return_1d");
    expect(analysis.calibration_drift.status).toBe("stable");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/analysis/2330", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses typed ticker warning history with a bounded limit", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(historyPayload("2330")));

    const history = await fetchTickerHistory("2330", 30);

    expect(history.ticker).toBe("2330");
    expect(history.records[0].warning_level).toBe("watch");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/analysis/2330/history?limit=30", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses warning transition timelines with a bounded limit", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(warningTransitionsPayload()));

    const transitions = await fetchTickerTransitions("NVDA", 30);

    expect(transitions.transitions[0].transition_type).toBe("new_alert");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/analysis/NVDA/transitions?limit=30", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses ticker coverage lists", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(tickerListPayload()));

    const tickers = await fetchTickers();

    expect(tickers.record_count).toBe(2);
    expect(tickers.tickers[0].ticker).toBe("2330");
    expect(tickers.tickers[0].market).toBe("taiwan");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/tickers", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses provider health and coverage observations", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(providerHealthPayload()));

    const health = await fetchProviderHealth();

    expect(health.records[0].status).toBe("healthy");
    expect(health.records[0].coverage).toBe("available");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/providers/health", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses DB-backed watchlists", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(watchlistPayload()));

    const watchlist = await fetchWatchlist("session-test");

    expect(watchlist.schema_version).toBe("watchlist.v1");
    expect(watchlist.tickers[0].query_symbol).toBe("2330.TW");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/session-test", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("parses emerging market watchlist tickers", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...watchlistPayload(),
        tickers: [
          {
            ...watchlistPayload().tickers[0],
            ticker: "5240",
            query_symbol: "5240.EMERGING",
            market: "emerging"
          }
        ]
      })
    );

    const watchlist = await fetchWatchlist("session-test");

    expect(watchlist.tickers[0].market).toBe("emerging");
    expect(watchlist.tickers[0].query_symbol).toBe("5240.EMERGING");
  });

  it("adds watchlist tickers with a schema-first request body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(watchlistPayload(), 201));

    const watchlist = await addWatchlistTicker("2330", "session-test");

    expect(watchlist.record_count).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/session-test/tickers", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        schema_version: "watchlist_add.v1",
        ticker: "2330",
        market: "auto",
        notes: ""
      })
    });
  });

  it("removes watchlist tickers through the typed API client", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...watchlistPayload(), record_count: 0, tickers: [] }));

    const watchlist = await removeWatchlistTicker("2330", "session-test");

    expect(watchlist.record_count).toBe(0);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/session-test/tickers/2330", {
      method: "DELETE",
      headers: {
        Accept: "application/json"
      },
      body: undefined
    });
  });

  it("uses the typed API error envelope when available", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: { code: "ticker_not_found", message: "ticker not found" } }, 404)
    );

    await expect(fetchTickerAnalysis("9999")).rejects.toMatchObject({
      code: "ticker_not_found",
      status: 404
    } satisfies Partial<APIClientError>);
  });

  it("returns a typed error for empty API responses", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 404 }));

    await expect(fetchStatus()).rejects.toMatchObject({
      code: "empty_response",
      status: 404
    } satisfies Partial<APIClientError>);
  });

  it("returns a typed error for non-JSON API responses", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("<html>bad gateway</html>", {
        status: 502,
        headers: {
          "content-type": "text/html"
        }
      })
    );

    await expect(fetchStatus()).rejects.toMatchObject({
      code: "invalid_json_response",
      status: 502
    } satisfies Partial<APIClientError>);
  });
});
