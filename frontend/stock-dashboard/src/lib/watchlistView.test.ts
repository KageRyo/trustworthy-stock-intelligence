import { describe, expect, it } from "vitest";
import {
  addGroup,
  assignTickerToGroup,
  defaultWatchlistFilters,
  filterWatchlistTickers,
  removeGroup,
  sortWatchlistTickers,
  type WatchlistGroupingState
} from "./watchlistView";
import type { WatchlistTicker } from "./schemas";

const tickers: WatchlistTicker[] = [
  {
    ticker: "NVDA",
    query_symbol: "NVDA",
    market: "us",
    added_at: "2026-08-12T00:00:00Z",
    notes: "",
    has_latest_warning: true,
    latest_warning: {
      date: "2026-08-12",
      warning_level: "alert",
      calibrated_risk_probability: 0.7,
      trust_score: 0.2,
      alert_threshold: 0.5,
      freshness_state: "stale"
    }
  },
  {
    ticker: "2330",
    query_symbol: "2330.TW",
    market: "twse",
    added_at: "2026-08-13T00:00:00Z",
    notes: "",
    has_latest_warning: true,
    latest_warning: {
      date: "2026-08-13",
      warning_level: "watch",
      calibrated_risk_probability: 0.3,
      trust_score: 0.8,
      alert_threshold: 0.5,
      freshness_state: "fresh"
    }
  }
];

describe("watchlist view helpers", () => {
  it("groups and ungroups session tickers", () => {
    let state: WatchlistGroupingState = addGroup({ groups: [], assignments: {} }, "Core");
    state = assignTickerToGroup(state, "NVDA", "Core");
    expect(state.assignments.NVDA).toBe("Core");
    state = removeGroup(state, "Core");
    expect(state.groups).toEqual([]);
    expect(state.assignments.NVDA).toBeUndefined();
  });

  it("filters by market, warning, low trust, freshness, and group", () => {
    const grouping = assignTickerToGroup({ groups: [], assignments: {} }, "NVDA", "Core");
    expect(filterWatchlistTickers(tickers, { ...defaultWatchlistFilters, market: "us" }, grouping).map((ticker) => ticker.ticker)).toEqual(["NVDA"]);
    expect(filterWatchlistTickers(tickers, { ...defaultWatchlistFilters, warning: "watch" }, grouping).map((ticker) => ticker.ticker)).toEqual(["2330"]);
    expect(filterWatchlistTickers(tickers, { ...defaultWatchlistFilters, trust: "low" }, grouping).map((ticker) => ticker.ticker)).toEqual(["NVDA"]);
    expect(filterWatchlistTickers(tickers, { ...defaultWatchlistFilters, freshness: "stale" }, grouping).map((ticker) => ticker.ticker)).toEqual(["NVDA"]);
    expect(filterWatchlistTickers(tickers, { ...defaultWatchlistFilters, group: "Core" }, grouping).map((ticker) => ticker.ticker)).toEqual(["NVDA"]);
  });

  it("sorts by warning severity, trust, and newest addition", () => {
    expect(sortWatchlistTickers(tickers, "warning").map((ticker) => ticker.ticker)).toEqual(["NVDA", "2330"]);
    expect(sortWatchlistTickers(tickers, "trust").map((ticker) => ticker.ticker)).toEqual(["NVDA", "2330"]);
    expect(sortWatchlistTickers(tickers, "added").map((ticker) => ticker.ticker)).toEqual(["2330", "NVDA"]);
  });
});
