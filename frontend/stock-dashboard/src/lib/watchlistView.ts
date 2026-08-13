import type { WatchlistTicker, WarningLevel } from "./schemas";

export type WatchlistGroup = "" | string;
export type WatchlistMarketFilter = "all" | "us" | "twse" | "tpex" | "emerging" | "taiwan" | "unknown";
export type WatchlistWarningFilter = "all" | WarningLevel;
export type WatchlistTrustFilter = "all" | "low";
export type WatchlistFreshnessFilter = "all" | "fresh" | "stale" | "unusable";
export type WatchlistSort = "ticker" | "market" | "warning" | "trust" | "freshness" | "added";

export type WatchlistFilters = {
  group: WatchlistGroup;
  market: WatchlistMarketFilter;
  warning: WatchlistWarningFilter;
  trust: WatchlistTrustFilter;
  freshness: WatchlistFreshnessFilter;
};

export type WatchlistGroupingState = {
  groups: string[];
  assignments: Record<string, string>;
};

export const defaultWatchlistFilters: WatchlistFilters = {
  group: "",
  market: "all",
  warning: "all",
  trust: "all",
  freshness: "all"
};

export const defaultWatchlistGroupingState: WatchlistGroupingState = {
  groups: [],
  assignments: {}
};

export const watchlistGroupingStorageKey = "tsi.session.watchlist.groups";

const warningRank: Record<WarningLevel, number> = {
  alert: 0,
  watch: 1,
  abstain: 2,
  no_alert: 3
};

function normalizedGroup(value: string): string {
  return value.trim().replace(/\s+/g, " ").slice(0, 40);
}

export function groupForTicker(state: WatchlistGroupingState, ticker: string): string {
  return state.assignments[ticker.trim().toUpperCase()] ?? "";
}

export function addGroup(state: WatchlistGroupingState, group: string): WatchlistGroupingState {
  const normalized = normalizedGroup(group);
  if (!normalized || state.groups.includes(normalized)) {
    return state;
  }
  return { ...state, groups: [...state.groups, normalized].sort((left, right) => left.localeCompare(right)) };
}

export function removeGroup(state: WatchlistGroupingState, group: string): WatchlistGroupingState {
  const nextAssignments = { ...state.assignments };
  for (const [ticker, assignedGroup] of Object.entries(nextAssignments)) {
    if (assignedGroup === group) {
      delete nextAssignments[ticker];
    }
  }
  return { groups: state.groups.filter((entry) => entry !== group), assignments: nextAssignments };
}

export function assignTickerToGroup(
  state: WatchlistGroupingState,
  ticker: string,
  group: string
): WatchlistGroupingState {
  const key = ticker.trim().toUpperCase();
  const nextAssignments = { ...state.assignments };
  const normalized = normalizedGroup(group);
  if (!normalized) {
    delete nextAssignments[key];
  } else {
    nextAssignments[key] = normalized;
  }
  return { ...addGroup(state, normalized), assignments: nextAssignments };
}

export function filterWatchlistTickers(
  tickers: WatchlistTicker[],
  filters: WatchlistFilters,
  grouping: WatchlistGroupingState
): WatchlistTicker[] {
  return tickers.filter((ticker) => {
    const warning = ticker.latest_warning;
    const tickerGroup = groupForTicker(grouping, ticker.ticker);
    if (filters.group === "ungrouped" && tickerGroup) return false;
    if (filters.group && filters.group !== "ungrouped" && tickerGroup !== filters.group) return false;
    if (filters.market !== "all" && ticker.market !== filters.market) return false;
    if (filters.warning !== "all" && warning?.warning_level !== filters.warning) return false;
    if (filters.trust === "low" && (!warning || warning.alert_threshold === undefined || warning.trust_score >= warning.alert_threshold)) {
      return false;
    }
    if (filters.freshness !== "all" && warning?.freshness_state !== filters.freshness) return false;
    return true;
  });
}

export function sortWatchlistTickers(tickers: WatchlistTicker[], sort: WatchlistSort): WatchlistTicker[] {
  const sorted = [...tickers];
  sorted.sort((left, right) => {
    const leftWarning = left.latest_warning;
    const rightWarning = right.latest_warning;
    switch (sort) {
      case "market":
        return left.market.localeCompare(right.market) || left.ticker.localeCompare(right.ticker);
      case "warning":
        return (leftWarning ? warningRank[leftWarning.warning_level] : 99) -
          (rightWarning ? warningRank[rightWarning.warning_level] : 99) || left.ticker.localeCompare(right.ticker);
      case "trust":
        return (leftWarning?.trust_score ?? Number.POSITIVE_INFINITY) -
          (rightWarning?.trust_score ?? Number.POSITIVE_INFINITY) || left.ticker.localeCompare(right.ticker);
      case "freshness":
        return (leftWarning?.freshness_state ?? "unknown").localeCompare(rightWarning?.freshness_state ?? "unknown") || left.ticker.localeCompare(right.ticker);
      case "added":
        return right.added_at.localeCompare(left.added_at) || left.ticker.localeCompare(right.ticker);
      case "ticker":
      default:
        return left.ticker.localeCompare(right.ticker);
    }
  });
  return sorted;
}

export function loadWatchlistGroupingState(watchlistName: string): WatchlistGroupingState {
  if (typeof window === "undefined") return defaultWatchlistGroupingState;
  try {
    const raw = window.sessionStorage.getItem(`${watchlistGroupingStorageKey}:${watchlistName}`);
    if (!raw) return defaultWatchlistGroupingState;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return defaultWatchlistGroupingState;
    const value = parsed as Partial<WatchlistGroupingState>;
    const groups = Array.isArray(value.groups)
      ? value.groups.filter((group): group is string => typeof group === "string").map(normalizedGroup).filter(Boolean)
      : [];
    const assignments = value.assignments && typeof value.assignments === "object"
      ? Object.fromEntries(Object.entries(value.assignments).filter((entry): entry is [string, string] => typeof entry[1] === "string"))
      : {};
    return { groups: [...new Set(groups)].sort((left, right) => left.localeCompare(right)), assignments };
  } catch {
    return defaultWatchlistGroupingState;
  }
}

export function saveWatchlistGroupingState(watchlistName: string, state: WatchlistGroupingState): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(`${watchlistGroupingStorageKey}:${watchlistName}`, JSON.stringify(state));
  } catch {
    // Session grouping is an enhancement; the DB-backed watchlist remains usable.
  }
}
