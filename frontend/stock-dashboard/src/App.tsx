import {
  Activity,
  AlertTriangle,
  Database,
  Gauge,
  Info,
  ListChecks,
  RefreshCcw,
  Search,
  ShieldCheck,
  Target,
  Trash2
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  APIClientError,
  addWatchlistTicker,
  fetchCurrentModel,
  fetchLatestWarnings,
  fetchStatus,
  fetchTickerAnalysis,
  fetchTickers,
  fetchWatchlist,
  removeWatchlistTicker
} from "./lib/api";
import type {
  APIStatus,
  CurrentModel,
  PredictionBatch,
  PredictionRecord,
  ReasonExplanation,
  TickerList,
  TickerAnalysis,
  Watchlist,
  WatchlistTicker,
  WarningLevel
} from "./lib/schemas";

type LoadState = "idle" | "loading" | "ready" | "error";

const levelStyles: Record<WarningLevel, string> = {
  alert: "border-red-200 bg-red-50 text-red-800",
  watch: "border-amber-200 bg-amber-50 text-amber-800",
  abstain: "border-sky-200 bg-sky-50 text-sky-800",
  no_alert: "border-emerald-200 bg-emerald-50 text-emerald-800"
};

const levelLabels: Record<WarningLevel, string> = {
  alert: "Alert",
  watch: "Watch",
  abstain: "Abstain",
  no_alert: "No Alert"
};

const barColors = ["#c2410c", "#0369a1", "#166534", "#b45309"];
const sessionWatchlistStorageKey = "tsi.session.watchlist_name";

function formatPercent(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toLocaleString("en-US");
}

function errorMessage(error: unknown): string {
  if (error instanceof APIClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function normalizeTicker(value: string): string {
  return value.trim().toUpperCase();
}

function createSessionWatchlistName(): string {
  const randomID =
    typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `session-${randomID.replace(/[^a-zA-Z0-9-]/g, "")}`;
}

function getSessionWatchlistName(): string {
  if (typeof window === "undefined") {
    return createSessionWatchlistName();
  }
  try {
    const existing = window.sessionStorage.getItem(sessionWatchlistStorageKey);
    if (existing) {
      return existing;
    }
    const nextName = createSessionWatchlistName();
    window.sessionStorage.setItem(sessionWatchlistStorageKey, nextName);
    return nextName;
  } catch {
    return createSessionWatchlistName();
  }
}

function summarizeBatch(batch: PredictionBatch | null) {
  const records = batch?.records ?? [];
  const counts: Record<WarningLevel, number> = {
    alert: 0,
    watch: 0,
    abstain: 0,
    no_alert: 0
  };
  for (const record of records) {
    counts[record.warning_level] += 1;
  }
  const averageTrust =
    records.length > 0
      ? records.reduce((sum, record) => sum + record.trust_score, 0) / records.length
      : undefined;
  const highestRisk = records[0];
  const lowestTrust = records.reduce<PredictionRecord | undefined>((current, record) => {
    if (!current || record.trust_score < current.trust_score) {
      return record;
    }
    return current;
  }, undefined);

  return {
    counts,
    averageTrust,
    highestRisk,
    lowestTrust
  };
}

function summarizeCoverage(tickerList: TickerList | null): string {
  if (!tickerList || tickerList.tickers.length === 0) {
    return "n/a";
  }
  const usCount = tickerList.tickers.filter((ticker) => ticker.market === "us").length;
  const taiwanCount = tickerList.tickers.filter((ticker) => ticker.market === "taiwan").length;
  const unknownCount = tickerList.tickers.length - usCount - taiwanCount;
  const parts = [];
  if (usCount > 0) {
    parts.push(`${usCount} US`);
  }
  if (taiwanCount > 0) {
    parts.push(`${taiwanCount} TW`);
  }
  if (unknownCount > 0) {
    parts.push(`${unknownCount} unknown`);
  }
  return parts.join(" / ");
}

export default function App() {
  const [watchlistName] = useState(getSessionWatchlistName);
  const [status, setStatus] = useState<APIStatus | null>(null);
  const [model, setModel] = useState<CurrentModel | null>(null);
  const [latestWarnings, setLatestWarnings] = useState<PredictionBatch | null>(null);
  const [tickerList, setTickerList] = useState<TickerList | null>(null);
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null);
  const [analysis, setAnalysis] = useState<TickerAnalysis | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [selectedTicker, setSelectedTicker] = useState("");
  const [batchState, setBatchState] = useState<LoadState>("idle");
  const [analysisState, setAnalysisState] = useState<LoadState>("idle");
  const [batchError, setBatchError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisNotice, setAnalysisNotice] = useState("");
  const [watchlistError, setWatchlistError] = useState("");

  const batchSummary = useMemo(() => summarizeBatch(latestWarnings), [latestWarnings]);
  const coverageSummary = useMemo(() => summarizeCoverage(tickerList), [tickerList]);

  const loadBatch = useCallback(async () => {
    setBatchState("loading");
    setBatchError("");
    try {
      const [nextStatus, nextModel, nextWarnings, nextTickers, nextWatchlist] = await Promise.all([
        fetchStatus(),
        fetchCurrentModel(),
        fetchLatestWarnings(75),
        fetchTickers(),
        fetchWatchlist(watchlistName)
      ]);
      setStatus(nextStatus);
      setModel(nextModel);
      setLatestWarnings(nextWarnings);
      setTickerList(nextTickers);
      setWatchlist(nextWatchlist);
      setWatchlistError("");
      setBatchState("ready");
    } catch (error) {
      setBatchError(errorMessage(error));
      setBatchState("error");
    }
  }, [watchlistName]);

  const rememberViewedTicker = useCallback(
    async (ticker: string) => {
      const nextWatchlist = await addWatchlistTicker(ticker, watchlistName);
      setWatchlist(nextWatchlist);
      setWatchlistError("");
      const hasLatestWarning = nextWatchlist.tickers.some(
        (entry) => entry.ticker === ticker && entry.has_latest_warning
      );
      if (!hasLatestWarning) {
        setAnalysisNotice(`${ticker} was analyzed, but the watchlist join has not refreshed yet.`);
      }
    },
    [watchlistName]
  );

  const loadAnalysis = useCallback(async (ticker: string) => {
    const normalized = normalizeTicker(ticker);
    if (!normalized) {
      return;
    }
    setAnalysisState("loading");
    setAnalysisError("");
    setAnalysisNotice("");
    try {
      const nextAnalysis = await fetchTickerAnalysis(normalized);
      setAnalysis(nextAnalysis);
      setAnalysisState("ready");
      try {
        await rememberViewedTicker(normalized);
      } catch (watchlistAddError) {
        setWatchlistError(errorMessage(watchlistAddError));
      }
    } catch (error) {
      setAnalysis(null);
      if (error instanceof APIClientError && error.code === "ticker_not_found") {
        setAnalysisError(
          `No market data or model output could be generated for ${normalized}. Check the symbol and provider coverage.`
        );
        setAnalysisState("error");
        return;
      }
      setAnalysisError(errorMessage(error));
      setAnalysisState("error");
    }
  }, [rememberViewedTicker]);

  useEffect(() => {
    void loadBatch();
  }, [loadBatch]);

  useEffect(() => {
    if (selectedTicker) {
      void loadAnalysis(selectedTicker);
    }
  }, [loadAnalysis, selectedTicker]);

  function submitTicker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = normalizeTicker(tickerInput);
    if (normalized) {
      setSelectedTicker(normalized);
    }
  }

  function refreshAll() {
    void loadBatch();
    if (selectedTicker) {
      void loadAnalysis(selectedTicker);
    }
  }

  async function removeTickerFromWatchlist(ticker: string) {
    setWatchlistError("");
    try {
      const nextWatchlist = await removeWatchlistTicker(ticker, watchlistName);
      setWatchlist(nextWatchlist);
    } catch (error) {
      setWatchlistError(errorMessage(error));
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-line pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-normal text-data">
              Trustworthy Stock Intelligence
            </p>
            <h1 className="text-2xl font-semibold tracking-normal sm:text-3xl">
              Stock Risk Dashboard
            </h1>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <form
              className="flex min-w-0 rounded-md border border-line bg-white shadow-sm"
              onSubmit={submitTicker}
            >
              <input
                className="h-11 min-w-0 flex-1 rounded-l-md px-3 text-sm font-medium outline-none ring-0 placeholder:text-slate-400 sm:w-48"
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                placeholder="Ticker or 2330"
                aria-label="Ticker or Taiwan stock code"
              />
              <button
                className="inline-flex h-11 items-center gap-2 rounded-r-md bg-ink px-4 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-data"
                type="submit"
              >
                <Search size={17} aria-hidden="true" />
                Search
              </button>
            </form>
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-data"
              type="button"
              onClick={refreshAll}
            >
              <RefreshCcw size={17} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </header>

        {batchError ? <ErrorBanner message={batchError} /> : null}
        {watchlistError ? <ErrorBanner message={watchlistError} /> : null}
        {status?.last_error ? <ErrorBanner message={status.last_error} /> : null}

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard
            icon={<AlertTriangle size={18} />}
            label="Alerts"
            value={formatNumber(batchSummary.counts.alert)}
            tone="risk"
          />
          <MetricCard
            icon={<Target size={18} />}
            label="Watch"
            value={formatNumber(batchSummary.counts.watch)}
            tone="watch"
          />
          <MetricCard
            icon={<ShieldCheck size={18} />}
            label="Avg Trust"
            value={formatPercent(batchSummary.averageTrust)}
            tone="trust"
          />
          <MetricCard
            icon={<Gauge size={18} />}
            label="Highest Risk"
            value={batchSummary.highestRisk?.ticker ?? "n/a"}
            detail={formatPercent(batchSummary.highestRisk?.calibrated_risk_probability)}
            tone="risk"
          />
          <MetricCard
            icon={<Activity size={18} />}
            label="Lowest Trust"
            value={batchSummary.lowestTrust?.ticker ?? "n/a"}
            detail={formatPercent(batchSummary.lowestTrust?.trust_score)}
            tone="watch"
          />
          <MetricCard
            icon={<Database size={18} />}
            label="Coverage"
            value={formatNumber(tickerList?.record_count ?? status?.record_count)}
            detail={`${coverageSummary} / Seen ${formatNumber(watchlist?.record_count)}`}
            tone="data"
          />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
          <AnalysisPanel
            analysis={analysis}
            state={analysisState}
            error={analysisError}
            notice={analysisNotice}
          />
          <TrustPanel analysis={analysis} model={model} status={status} />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <WatchlistPanel
            watchlist={watchlist}
            watchlistName={watchlistName}
            selectedTicker={selectedTicker}
            onSelectTicker={(ticker) => {
              setTickerInput(ticker);
              setSelectedTicker(ticker);
            }}
            onRemoveTicker={removeTickerFromWatchlist}
          />
          <WarningsTable
            records={latestWarnings?.records ?? []}
            selectedTicker={selectedTicker}
            onSelectTicker={(ticker) => {
              setTickerInput(ticker);
              setSelectedTicker(ticker);
            }}
            loading={batchState === "loading"}
          />
        </section>

        <section>
          <ReasonsPanel reasons={analysis?.reasons ?? []} />
        </section>
      </div>
    </main>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
  tone
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
  tone: "risk" | "watch" | "trust" | "data";
}) {
  const toneClass = {
    risk: "text-risk bg-orange-50",
    watch: "text-watch bg-amber-50",
    trust: "text-trust bg-emerald-50",
    data: "text-data bg-sky-50"
  }[tone];

  return (
    <div className="min-h-[104px] rounded-lg border border-line bg-white p-4 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-normal text-slate-500">{label}</span>
        <span className={`grid h-8 w-8 place-items-center rounded-md ${toneClass}`}>{icon}</span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <span className="truncate text-2xl font-semibold tracking-normal">{value}</span>
        {detail ? <span className="pb-1 text-sm font-medium text-slate-500">{detail}</span> : null}
      </div>
    </div>
  );
}

function AnalysisPanel({
  analysis,
  state,
  error,
  notice
}: {
  analysis: TickerAnalysis | null;
  state: LoadState;
  error: string;
  notice: string;
}) {
  const chartData = analysis
    ? [
        { name: "Risk", value: analysis.warning.risk_probability },
        { name: "Calibrated", value: analysis.warning.calibrated_risk_probability },
        { name: "Trust", value: analysis.trust.trust_score },
        { name: "Uncertainty", value: analysis.trust.uncertainty_score }
      ]
    : [];

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold tracking-normal">
              {analysis?.ticker ?? "Ticker Analysis"}
            </h2>
            {analysis ? <LevelBadge level={analysis.warning.level} /> : null}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {analysis ? `${analysis.date} | ${analysis.run_id}` : "No ticker selected"}
          </p>
        </div>
        {analysis ? (
          <div className="text-right">
            <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">
              Calibrated Risk
            </p>
            <p className="text-3xl font-semibold tracking-normal text-risk">
              {formatPercent(analysis.warning.calibrated_risk_probability)}
            </p>
          </div>
        ) : null}
      </div>

      {state === "loading" ? <PanelState label="Loading analysis" /> : null}
      {state === "error" ? <ErrorBanner message={error} /> : null}
      {notice ? <NoticeBanner message={notice} /> : null}

      {analysis ? (
        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(260px,0.7fr)]">
          <div className="min-h-[260px]">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
                <CartesianGrid stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis domain={[0, 1]} tickFormatter={(value) => `${Number(value) * 100}%`} />
                <Tooltip formatter={(value) => formatPercent(Number(value))} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={entry.name} fill={barColors[index % barColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid content-start gap-3">
            <ValueRow label="Raw Risk" value={formatPercent(analysis.warning.risk_probability)} />
            <ValueRow
              label="Calibrated Risk"
              value={formatPercent(analysis.warning.calibrated_risk_probability)}
            />
            <ValueRow label="Alert Threshold" value={formatPercent(analysis.warning.alert_threshold)} />
            <ValueRow label="Watch Threshold" value={formatPercent(analysis.warning.watch_threshold)} />
            <p className="rounded-md border border-line bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              {analysis.warning.summary}
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TrustPanel({
  analysis,
  model,
  status
}: {
  analysis: TickerAnalysis | null;
  model: CurrentModel | null;
  status: APIStatus | null;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex items-center justify-between border-b border-line pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">Trust And Model</h2>
          <p className="mt-1 text-sm text-slate-500">{model?.model || analysis?.model.name || "n/a"}</p>
        </div>
        <ShieldCheck className="text-trust" size={24} aria-hidden="true" />
      </div>
      <div className="mt-5 grid gap-3">
        <ValueRow label="Trust Score" value={formatPercent(analysis?.trust.trust_score)} />
        <ValueRow label="Trust Status" value={analysis?.trust.trust_status ?? "n/a"} />
        <ValueRow label="Uncertainty" value={formatPercent(analysis?.trust.uncertainty_score)} />
        <ValueRow label="Uncertainty Status" value={analysis?.trust.uncertainty_status ?? "n/a"} />
        <ValueRow label="Calibration" value={analysis?.trust.calibration_method ?? "n/a"} />
        <ValueRow label="Data As Of" value={status?.data_as_of || analysis?.data_as_of || "n/a"} />
        <ValueRow label="Generated At" value={status?.generated_at || analysis?.generated_at || "n/a"} />
        <ValueRow label="Model Bundle" value={model?.model_bundle || analysis?.model.model_bundle || "n/a"} />
      </div>
      {analysis ? (
        <p className="mt-4 rounded-md border border-line bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
          {analysis.trust.summary}
        </p>
      ) : null}
    </section>
  );
}

function ReasonsPanel({ reasons }: { reasons: ReasonExplanation[] }) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between border-b border-line pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">Reason Codes</h2>
          <p className="mt-1 text-sm text-slate-500">{formatNumber(reasons.length)} reasons</p>
        </div>
        <Info className="text-data" size={22} aria-hidden="true" />
      </div>
      <div className="grid gap-3">
        {reasons.length === 0 ? <PanelState label="No reason codes" /> : null}
        {reasons.map((reason) => (
          <ReasonItem key={reason.code} reason={reason} />
        ))}
      </div>
    </section>
  );
}

function ReasonItem({ reason }: { reason: ReasonExplanation }) {
  const severityClass = {
    alert: "border-red-200 bg-red-50 text-red-900",
    watch: "border-amber-200 bg-amber-50 text-amber-900",
    info: "border-sky-200 bg-sky-50 text-sky-900"
  }[reason.severity];

  return (
    <div className={`rounded-md border p-3 ${severityClass}`}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-semibold">{reason.title}</p>
        <span className="text-xs font-semibold uppercase tracking-normal">{reason.severity}</span>
      </div>
      <p className="mt-2 text-sm leading-6">{reason.detail}</p>
      <p className="mt-2 break-all font-mono text-xs opacity-75">{reason.code}</p>
    </div>
  );
}

function WatchlistPanel({
  watchlist,
  watchlistName,
  selectedTicker,
  onSelectTicker,
  onRemoveTicker
}: {
  watchlist: Watchlist | null;
  watchlistName: string;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  onRemoveTicker: (ticker: string) => void;
}) {
  const tickers = watchlist?.tickers ?? [];

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">Session Watchlist</h2>
          <p className="mt-1 text-sm text-slate-500">
            {formatNumber(watchlist?.record_count)} viewed | {watchlistName}
          </p>
        </div>
        <ListChecks className="text-data" size={22} aria-hidden="true" />
      </div>
      {tickers.length === 0 ? <PanelState label="No viewed tickers in this session" /> : null}
      {tickers.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-[620px] w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
                <th className="py-3 pr-3 font-semibold">Ticker</th>
                <th className="px-3 py-3 font-semibold">Market</th>
                <th className="px-3 py-3 font-semibold">Latest</th>
                <th className="px-3 py-3 font-semibold">Trust</th>
                <th className="px-3 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {tickers.map((ticker) => (
                <WatchlistRow
                  key={`${ticker.market}-${ticker.ticker}`}
                  ticker={ticker}
                  selected={selectedTicker === ticker.ticker}
                  onSelectTicker={onSelectTicker}
                  onRemoveTicker={onRemoveTicker}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function WatchlistRow({
  ticker,
  selected,
  onSelectTicker,
  onRemoveTicker
}: {
  ticker: WatchlistTicker;
  selected: boolean;
  onSelectTicker: (ticker: string) => void;
  onRemoveTicker: (ticker: string) => void;
}) {
  return (
    <tr className={`border-b border-line last:border-0 ${selected ? "bg-sky-50" : "hover:bg-slate-50"}`}>
      <td className="py-3 pr-3">
        <button
          className="font-semibold text-data hover:underline focus:outline-none focus:ring-2 focus:ring-data"
          type="button"
          onClick={() => onSelectTicker(ticker.ticker)}
        >
          {ticker.ticker}
        </button>
        <p className="mt-1 text-xs text-slate-500">{ticker.query_symbol}</p>
      </td>
      <td className="px-3 py-3 text-slate-600">{ticker.market.toUpperCase()}</td>
      <td className="px-3 py-3">
        {ticker.latest_warning ? (
          <LevelBadge level={ticker.latest_warning.warning_level} />
        ) : (
          <span className="inline-flex min-w-[86px] items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold uppercase tracking-normal text-slate-600">
            Pending
          </span>
        )}
      </td>
      <td className="px-3 py-3">
        {ticker.latest_warning ? formatPercent(ticker.latest_warning.trust_score) : "n/a"}
      </td>
      <td className="px-3 py-3">
        <button
          className="grid h-9 w-9 place-items-center rounded-md border border-line bg-white text-slate-600 hover:bg-red-50 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-data"
          type="button"
          aria-label={`Remove ${ticker.ticker}`}
          onClick={() => onRemoveTicker(ticker.ticker)}
        >
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </td>
    </tr>
  );
}

function WarningsTable({
  records,
  selectedTicker,
  onSelectTicker,
  loading
}: {
  records: PredictionRecord[];
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  loading: boolean;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">Latest Warnings</h2>
          <p className="mt-1 text-sm text-slate-500">{formatNumber(records.length)} rows</p>
        </div>
        {loading ? <span className="text-sm font-medium text-data">Loading</span> : null}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[760px] w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
              <th className="py-3 pr-3 font-semibold">Ticker</th>
              <th className="px-3 py-3 font-semibold">Level</th>
              <th className="px-3 py-3 font-semibold">Calibrated</th>
              <th className="px-3 py-3 font-semibold">Trust</th>
              <th className="px-3 py-3 font-semibold">Uncertainty</th>
              <th className="px-3 py-3 font-semibold">Date</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr
                key={`${record.ticker}-${record.date}`}
                className={`border-b border-line last:border-0 ${
                  selectedTicker === record.ticker ? "bg-sky-50" : "hover:bg-slate-50"
                }`}
              >
                <td className="py-3 pr-3">
                  <button
                    className="font-semibold text-data hover:underline focus:outline-none focus:ring-2 focus:ring-data"
                    type="button"
                    onClick={() => onSelectTicker(record.ticker)}
                  >
                    {record.ticker}
                  </button>
                </td>
                <td className="px-3 py-3">
                  <LevelBadge level={record.warning_level} />
                </td>
                <td className="px-3 py-3 font-medium">
                  {formatPercent(record.calibrated_risk_probability)}
                </td>
                <td className="px-3 py-3">{formatPercent(record.trust_score)}</td>
                <td className="px-3 py-3">{formatPercent(record.uncertainty_score)}</td>
                <td className="px-3 py-3 text-slate-500">{record.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LevelBadge({ level }: { level: WarningLevel }) {
  return (
    <span
      className={`inline-flex min-w-[86px] items-center justify-center rounded-md border px-2.5 py-1 text-xs font-semibold uppercase tracking-normal ${levelStyles[level]}`}
    >
      {levelLabels[level]}
    </span>
  );
}

function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-h-[38px] items-center justify-between gap-4 border-b border-line pb-2 last:border-0">
      <span className="text-sm font-medium text-slate-500">{label}</span>
      <span className="max-w-[60%] truncate text-right text-sm font-semibold text-ink">{value}</span>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-900">
      {message}
    </div>
  );
}

function NoticeBanner({ message }: { message: string }) {
  return (
    <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-medium text-sky-900">
      {message}
    </div>
  );
}

function PanelState({ label }: { label: string }) {
  return (
    <div className="grid min-h-[120px] place-items-center rounded-md border border-dashed border-line bg-slate-50 text-sm font-medium text-slate-500">
      {label}
    </div>
  );
}
