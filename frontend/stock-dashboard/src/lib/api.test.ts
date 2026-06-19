import { afterEach, describe, expect, it, vi } from "vitest";
import {
  APIClientError,
  addWatchlistTicker,
  fetchStatus,
  fetchTickerAnalysis,
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
    warnings_path: "data/artifacts/latest_warnings.json",
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
      record_count: 2
    },
    reasons: [
      {
        code: "probability_above_watch_threshold",
        severity: "watch",
        title: "Risk probability above watch threshold",
        detail: "The calibrated risk probability is at or above the configured watch threshold."
      }
    ],
    limitations: ["This is a drawdown-risk warning signal, not investment advice."]
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
    name: "default",
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

  it("supports numeric Taiwan stock codes in analysis URLs", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(analysisPayload("2330")));

    const analysis = await fetchTickerAnalysis("2330");

    expect(analysis.ticker).toBe("2330");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/analysis/2330", {
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

  it("parses DB-backed watchlists", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(watchlistPayload()));

    const watchlist = await fetchWatchlist();

    expect(watchlist.schema_version).toBe("watchlist.v1");
    expect(watchlist.tickers[0].query_symbol).toBe("2330.TW");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/default", {
      headers: {
        Accept: "application/json"
      }
    });
  });

  it("adds watchlist tickers with a schema-first request body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(watchlistPayload(), 201));

    const watchlist = await addWatchlistTicker("2330");

    expect(watchlist.record_count).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/default/tickers", {
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

    const watchlist = await removeWatchlistTicker("2330");

    expect(watchlist.record_count).toBe(0);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/watchlists/default/tickers/2330", {
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
