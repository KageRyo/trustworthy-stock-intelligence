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
  Legend,
  Line,
  LineChart,
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
  fetchTickerHistory,
  fetchTickers,
  fetchWatchlist,
  removeWatchlistTicker
} from "./lib/api";
import {
  numberLocale,
  readStoredLocale,
  storeLocale,
  translations,
  type DashboardCopy,
  type Locale
} from "./lib/i18n";
import type {
  APIStatus,
  CurrentModel,
  FeatureAttribution,
  PredictionBatch,
  PredictionRecord,
  ReasonExplanation,
  TickerList,
  TickerAnalysis,
  WarningHistory,
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

const barColors = ["#c2410c", "#0369a1", "#166534", "#b45309"];
const sessionWatchlistStorageKey = "tsi.session.watchlist_name";

function formatPercent(value: number | undefined, na = "n/a"): string {
  if (value === undefined || Number.isNaN(value)) {
    return na;
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | undefined, locale: Locale, na = "n/a"): string {
  if (value === undefined || Number.isNaN(value)) {
    return na;
  }
  return value.toLocaleString(numberLocale(locale));
}

function errorMessage(error: unknown, copy: DashboardCopy): string {
  if (error instanceof APIClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return copy.errors.unexpected;
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

function summarizeCoverage(tickerList: TickerList | null, copy: DashboardCopy): string {
  if (!tickerList || tickerList.tickers.length === 0) {
    return copy.common.na;
  }
  const usCount = tickerList.tickers.filter((ticker) => ticker.market === "us").length;
  const taiwanCount = tickerList.tickers.filter((ticker) => ticker.market === "taiwan").length;
  const unknownCount = tickerList.tickers.length - usCount - taiwanCount;
  const parts = [];
  if (usCount > 0) {
    parts.push(`${usCount} ${copy.markets.us}`);
  }
  if (taiwanCount > 0) {
    parts.push(`${taiwanCount} ${copy.markets.taiwan}`);
  }
  if (unknownCount > 0) {
    parts.push(`${unknownCount} ${copy.markets.unknown}`);
  }
  return parts.join(" / ");
}

function hasReason(analysis: TickerAnalysis, code: string): boolean {
  return analysis.reasons.some((reason) => reason.code === code);
}

function localizedTrustSummary(analysis: TickerAnalysis, copy: DashboardCopy): string {
  if (hasReason(analysis, "insufficient_history")) {
    return copy.trustSummaries.insufficientHistory;
  }
  if (hasReason(analysis, "uncertainty_above_threshold")) {
    return copy.trustSummaries.highUncertainty;
  }
  if (hasReason(analysis, "trust_above_alert_threshold")) {
    return copy.trustSummaries.trustedForAlert;
  }
  if (hasReason(analysis, "trust_below_alert_threshold")) {
    return copy.trustSummaries.limitedTrust;
  }
  return copy.trustSummaries.default;
}

export default function App() {
  const [watchlistName] = useState(getSessionWatchlistName);
  const [locale, setLocale] = useState<Locale>(readStoredLocale);
  const [status, setStatus] = useState<APIStatus | null>(null);
  const [model, setModel] = useState<CurrentModel | null>(null);
  const [latestWarnings, setLatestWarnings] = useState<PredictionBatch | null>(null);
  const [tickerList, setTickerList] = useState<TickerList | null>(null);
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null);
  const [analysis, setAnalysis] = useState<TickerAnalysis | null>(null);
  const [history, setHistory] = useState<WarningHistory | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [selectedTicker, setSelectedTicker] = useState("");
  const [batchState, setBatchState] = useState<LoadState>("idle");
  const [analysisState, setAnalysisState] = useState<LoadState>("idle");
  const [batchError, setBatchError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisNotice, setAnalysisNotice] = useState("");
  const [historyState, setHistoryState] = useState<LoadState>("idle");
  const [historyError, setHistoryError] = useState("");
  const [watchlistError, setWatchlistError] = useState("");

  const copy = translations[locale];
  const batchSummary = useMemo(() => summarizeBatch(latestWarnings), [latestWarnings]);
  const coverageSummary = useMemo(() => summarizeCoverage(tickerList, copy), [tickerList, copy]);

  function changeLocale(nextLocale: Locale) {
    setLocale(nextLocale);
    storeLocale(nextLocale);
  }

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
      setBatchError(errorMessage(error, copy));
      setBatchState("error");
    }
  }, [copy, watchlistName]);

  const rememberViewedTicker = useCallback(
    async (ticker: string) => {
      const nextWatchlist = await addWatchlistTicker(ticker, watchlistName);
      setWatchlist(nextWatchlist);
      setWatchlistError("");
      const hasLatestWarning = nextWatchlist.tickers.some(
        (entry) => entry.ticker === ticker && entry.has_latest_warning
      );
      if (!hasLatestWarning) {
        setAnalysisNotice(copy.notices.watchlistJoinNotRefreshed(ticker));
      }
    },
    [copy, watchlistName]
  );

  const loadAnalysis = useCallback(async (ticker: string) => {
    const normalized = normalizeTicker(ticker);
    if (!normalized) {
      return;
    }
    setAnalysisState("loading");
    setAnalysisError("");
    setAnalysisNotice("");
    setHistory(null);
    setHistoryState("loading");
    setHistoryError("");
    try {
      const nextAnalysis = await fetchTickerAnalysis(normalized);
      setAnalysis(nextAnalysis);
      setAnalysisState("ready");
      try {
        const nextHistory = await fetchTickerHistory(normalized);
        setHistory(nextHistory);
        setHistoryState("ready");
      } catch (historyLoadError) {
        setHistory(null);
        if (historyLoadError instanceof APIClientError && historyLoadError.code === "ticker_not_found") {
          setHistoryState("ready");
        } else {
          setHistoryError(errorMessage(historyLoadError, copy));
          setHistoryState("error");
        }
      }
      try {
        await rememberViewedTicker(normalized);
      } catch (watchlistAddError) {
        setWatchlistError(errorMessage(watchlistAddError, copy));
      }
    } catch (error) {
      setAnalysis(null);
      setHistory(null);
      setHistoryState("idle");
      if (error instanceof APIClientError && error.code === "ticker_not_found") {
        setAnalysisError(copy.errors.noMarketData(normalized));
        setAnalysisState("error");
        return;
      }
      setAnalysisError(errorMessage(error, copy));
      setAnalysisState("error");
    }
  }, [copy, rememberViewedTicker]);

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
      setWatchlistError(errorMessage(error, copy));
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-line pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-normal text-data">
              {copy.productName}
            </p>
            <h1 className="text-2xl font-semibold tracking-normal sm:text-3xl">
              {copy.appTitle}
            </h1>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div
              className="inline-flex h-11 rounded-md border border-line bg-white p-1 shadow-sm"
              aria-label={copy.language.label}
            >
              {(["zh-Hant", "en"] as const).map((option) => (
                <button
                  key={option}
                  className={`rounded px-3 text-sm font-semibold ${
                    locale === option ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-50"
                  }`}
                  type="button"
                  onClick={() => changeLocale(option)}
                >
                  {option === "zh-Hant" ? copy.language.zhHant : copy.language.english}
                </button>
              ))}
            </div>
            <form
              className="flex min-w-0 rounded-md border border-line bg-white shadow-sm"
              onSubmit={submitTicker}
            >
              <input
                className="h-11 min-w-0 flex-1 rounded-l-md px-3 text-sm font-medium outline-none ring-0 placeholder:text-slate-400 sm:w-48"
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                placeholder={copy.searchPlaceholder}
                aria-label={copy.searchAria}
              />
              <button
                className="inline-flex h-11 items-center gap-2 rounded-r-md bg-ink px-4 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-data"
                type="submit"
              >
                <Search size={17} aria-hidden="true" />
                {copy.common.search}
              </button>
            </form>
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-data"
              type="button"
              onClick={refreshAll}
            >
              <RefreshCcw size={17} aria-hidden="true" />
              {copy.common.refresh}
            </button>
          </div>
        </header>

        {batchError ? <ErrorBanner message={batchError} /> : null}
        {watchlistError ? <ErrorBanner message={watchlistError} /> : null}
        {status?.last_error ? <ErrorBanner message={status.last_error} /> : null}

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard
            icon={<AlertTriangle size={18} />}
            label={copy.metrics.alerts}
            value={formatNumber(batchSummary.counts.alert, locale, copy.common.na)}
            tone="risk"
          />
          <MetricCard
            icon={<Target size={18} />}
            label={copy.metrics.watch}
            value={formatNumber(batchSummary.counts.watch, locale, copy.common.na)}
            tone="watch"
          />
          <MetricCard
            icon={<ShieldCheck size={18} />}
            label={copy.metrics.avgTrust}
            value={formatPercent(batchSummary.averageTrust, copy.common.na)}
            tone="trust"
          />
          <MetricCard
            icon={<Gauge size={18} />}
            label={copy.metrics.highestRisk}
            value={batchSummary.highestRisk?.ticker ?? copy.common.na}
            detail={formatPercent(batchSummary.highestRisk?.calibrated_risk_probability, copy.common.na)}
            tone="risk"
          />
          <MetricCard
            icon={<Activity size={18} />}
            label={copy.metrics.lowestTrust}
            value={batchSummary.lowestTrust?.ticker ?? copy.common.na}
            detail={formatPercent(batchSummary.lowestTrust?.trust_score, copy.common.na)}
            tone="watch"
          />
          <MetricCard
            icon={<Database size={18} />}
            label={copy.metrics.coverage}
            value={formatNumber(tickerList?.record_count ?? status?.record_count, locale, copy.common.na)}
            detail={`${coverageSummary} / ${copy.common.viewed} ${formatNumber(
              watchlist?.record_count,
              locale,
              copy.common.na
            )}`}
            tone="data"
          />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
          <AnalysisPanel
            analysis={analysis}
            state={analysisState}
            error={analysisError}
            notice={analysisNotice}
            copy={copy}
          />
          <TrustPanel analysis={analysis} model={model} status={status} copy={copy} />
        </section>

        <WarningTimelinePanel
          history={history}
          state={historyState}
          error={historyError}
          copy={copy}
          locale={locale}
        />

        <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <WatchlistPanel
            watchlist={watchlist}
            watchlistName={watchlistName}
            selectedTicker={selectedTicker}
            locale={locale}
            copy={copy}
            onSelectTicker={(ticker) => {
              setTickerInput(ticker);
              setSelectedTicker(ticker);
            }}
            onRemoveTicker={removeTickerFromWatchlist}
          />
          <WarningsTable
            records={latestWarnings?.records ?? []}
            selectedTicker={selectedTicker}
            locale={locale}
            copy={copy}
            onSelectTicker={(ticker) => {
              setTickerInput(ticker);
              setSelectedTicker(ticker);
            }}
            loading={batchState === "loading"}
          />
        </section>

        <section>
          <ReasonsPanel reasons={analysis?.reasons ?? []} copy={copy} locale={locale} />
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
  notice,
  copy
}: {
  analysis: TickerAnalysis | null;
  state: LoadState;
  error: string;
  notice: string;
  copy: DashboardCopy;
}) {
  const chartData = analysis
    ? [
        { name: copy.chart.risk, value: analysis.warning.risk_probability },
        { name: copy.chart.calibrated, value: analysis.warning.calibrated_risk_probability },
        { name: copy.chart.trust, value: analysis.trust.trust_score },
        { name: copy.chart.uncertainty, value: analysis.trust.uncertainty_score }
      ]
    : [];

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold tracking-normal">
              {analysis?.ticker ?? copy.panels.tickerAnalysis}
            </h2>
            {analysis ? <LevelBadge level={analysis.warning.level} copy={copy} /> : null}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {analysis ? `${analysis.date} | ${analysis.run_id}` : copy.panels.noTickerSelected}
          </p>
        </div>
        {analysis ? (
          <div className="text-right">
            <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">
              {copy.panels.calibratedRisk}
            </p>
            <p className="text-3xl font-semibold tracking-normal text-risk">
              {formatPercent(analysis.warning.calibrated_risk_probability, copy.common.na)}
            </p>
          </div>
        ) : null}
      </div>

      {state === "loading" ? <PanelState label={copy.states.loadingAnalysis} /> : null}
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
                <Tooltip formatter={(value) => formatPercent(Number(value), copy.common.na)} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={entry.name} fill={barColors[index % barColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid content-start gap-3">
            <ValueRow
              label={copy.labels.rawRisk}
              value={formatPercent(analysis.warning.risk_probability, copy.common.na)}
            />
            <ValueRow
              label={copy.labels.calibratedRisk}
              value={formatPercent(analysis.warning.calibrated_risk_probability, copy.common.na)}
            />
            <ValueRow
              label={copy.labels.alertThreshold}
              value={formatPercent(analysis.warning.alert_threshold, copy.common.na)}
            />
            <ValueRow
              label={copy.labels.watchThreshold}
              value={formatPercent(analysis.warning.watch_threshold, copy.common.na)}
            />
            <p className="rounded-md border border-line bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              {copy.warningSummaries[analysis.warning.level]}
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
  status,
  copy
}: {
  analysis: TickerAnalysis | null;
  model: CurrentModel | null;
  status: APIStatus | null;
  copy: DashboardCopy;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex items-center justify-between border-b border-line pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">{copy.panels.trustAndModel}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {model?.model || analysis?.model.name || copy.common.na}
          </p>
        </div>
        <ShieldCheck className="text-trust" size={24} aria-hidden="true" />
      </div>
      <div className="mt-5 grid gap-3">
        <ValueRow
          label={copy.labels.trustScore}
          value={formatPercent(analysis?.trust.trust_score, copy.common.na)}
        />
        <ValueRow
          label={copy.labels.trustStatus}
          value={
            analysis
              ? copy.trustStatuses[analysis.trust.trust_status] ?? analysis.trust.trust_status
              : copy.common.na
          }
        />
        <ValueRow
          label={copy.labels.uncertainty}
          value={formatPercent(analysis?.trust.uncertainty_score, copy.common.na)}
        />
        <ValueRow
          label={copy.labels.uncertaintyStatus}
          value={
            analysis
              ? copy.uncertaintyStatuses[analysis.trust.uncertainty_status] ??
                analysis.trust.uncertainty_status
              : copy.common.na
          }
        />
        <ValueRow label={copy.labels.calibration} value={analysis?.trust.calibration_method ?? copy.common.na} />
        <ValueRow
          label={copy.labels.dataAsOf}
          value={status?.data_as_of || analysis?.data_as_of || copy.common.na}
        />
        <ValueRow
          label={copy.labels.generatedAt}
          value={status?.generated_at || analysis?.generated_at || copy.common.na}
        />
        <ValueRow
          label={copy.labels.modelBundle}
          value={model?.model_bundle || analysis?.model.model_bundle || copy.common.na}
        />
      </div>
      {analysis ? (
        <p className="mt-4 rounded-md border border-line bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
          {localizedTrustSummary(analysis, copy)}
        </p>
      ) : null}
      {analysis ? <FeatureAttributionList attributions={analysis.feature_attributions ?? []} copy={copy} /> : null}
    </section>
  );
}

function WarningTimelinePanel({
  history,
  state,
  error,
  copy,
  locale
}: {
  history: WarningHistory | null;
  state: LoadState;
  error: string;
  copy: DashboardCopy;
  locale: Locale;
}) {
  const records = history?.records ?? [];
  const chartData = records.map((record) => ({
    date: record.date,
    risk: record.risk_probability,
    calibrated: record.calibrated_risk_probability,
    trust: record.trust_score,
    uncertainty: record.uncertainty_score
  }));

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">{copy.panels.tickerTimeline}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {history?.ticker ?? copy.common.noAnalysis} · {formatNumber(records.length, locale, copy.common.na)} {copy.common.rows}
          </p>
        </div>
        <Activity className="text-data" size={22} aria-hidden="true" />
      </div>
      {state === "loading" ? <PanelState label={copy.states.loadingHistory} /> : null}
      {state === "error" ? <ErrorBanner message={error || copy.errors.historyUnavailable} /> : null}
      {state !== "loading" && state !== "error" && records.length === 0 ? (
        <PanelState label={copy.states.noHistory} />
      ) : null}
      {records.length > 0 ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.9fr)]">
          <div className="min-h-[300px]">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
                <CartesianGrid stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis domain={[0, 1]} tickFormatter={(value) => `${Number(value) * 100}%`} />
                <Tooltip formatter={(value) => formatPercent(Number(value), copy.common.na)} />
                <Legend />
                <Line type="monotone" dataKey="risk" name={copy.chart.risk} stroke="#c2410c" dot={false} />
                <Line
                  type="monotone"
                  dataKey="calibrated"
                  name={copy.chart.calibrated}
                  stroke="#0369a1"
                  dot={false}
                />
                <Line type="monotone" dataKey="trust" name={copy.chart.trust} stroke="#166534" dot={false} />
                <Line
                  type="monotone"
                  dataKey="uncertainty"
                  name={copy.chart.uncertainty}
                  stroke="#b45309"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="max-h-[300px] overflow-auto rounded-md border border-line">
            <table className="min-w-[520px] w-full border-collapse text-left text-sm">
              <thead className="sticky top-0 bg-slate-50">
                <tr className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
                  <th className="px-3 py-3 font-semibold">{copy.labels.date}</th>
                  <th className="px-3 py-3 font-semibold">{copy.labels.calibratedRisk}</th>
                  <th className="px-3 py-3 font-semibold">{copy.labels.trustScore}</th>
                  <th className="px-3 py-3 font-semibold">{copy.labels.uncertainty}</th>
                  <th className="px-3 py-3 font-semibold">{copy.labels.level}</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={`${record.run_id}-${record.date}`} className="border-b border-line last:border-0">
                    <td className="px-3 py-3 font-medium whitespace-nowrap">{record.date}</td>
                    <td className="px-3 py-3">{formatPercent(record.calibrated_risk_probability, copy.common.na)}</td>
                    <td className="px-3 py-3">{formatPercent(record.trust_score, copy.common.na)}</td>
                    <td className="px-3 py-3">{formatPercent(record.uncertainty_score, copy.common.na)}</td>
                    <td className="px-3 py-3">
                      <LevelBadge level={record.warning_level} copy={copy} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function FeatureAttributionList({
  attributions,
  copy
}: {
  attributions: FeatureAttribution[];
  copy: DashboardCopy;
}) {
  const sorted = [...attributions].sort(
    (left, right) => Math.abs(right.contribution) - Math.abs(left.contribution)
  );

  return (
    <div className="mt-5 rounded-md border border-line bg-slate-50 p-4">
      <h3 className="text-sm font-semibold text-ink">{copy.panels.featureAttributions}</h3>
      <p className="mt-1 text-xs leading-5 text-slate-600">{copy.attributionNote}</p>
      {sorted.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">{copy.common.na}</p>
      ) : (
        <div className="mt-3 grid gap-2">
          {sorted.map((attribution) => {
            const contributionClass =
              attribution.direction === "positive" ? "text-risk" : "text-trust";
            const sign = attribution.contribution >= 0 ? "+" : "";
            return (
              <div
                key={`${attribution.feature}-${attribution.method}`}
                className="flex items-center justify-between gap-3 rounded border border-line bg-white px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{attribution.feature}</p>
                  <p className="text-xs text-slate-500">
                    {attribution.value === null ? copy.common.na : attribution.value.toFixed(4)} · {attribution.method}
                  </p>
                </div>
                <span className={`shrink-0 font-mono text-sm font-semibold ${contributionClass}`}>
                  {sign}{attribution.contribution.toFixed(4)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ReasonsPanel({
  reasons,
  copy,
  locale
}: {
  reasons: ReasonExplanation[];
  copy: DashboardCopy;
  locale: Locale;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between border-b border-line pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">{copy.panels.reasonCodes}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {formatNumber(reasons.length, locale, copy.common.na)} {copy.common.reasons}
          </p>
        </div>
        <Info className="text-data" size={22} aria-hidden="true" />
      </div>
      <div className="grid gap-3">
        {reasons.length === 0 ? <PanelState label={copy.states.noReasonCodes} /> : null}
        {reasons.map((reason) => (
          <ReasonItem key={reason.code} reason={reason} copy={copy} />
        ))}
      </div>
    </section>
  );
}

function ReasonItem({ reason, copy }: { reason: ReasonExplanation; copy: DashboardCopy }) {
  const severityClass = {
    alert: "border-red-200 bg-red-50 text-red-900",
    watch: "border-amber-200 bg-amber-50 text-amber-900",
    info: "border-sky-200 bg-sky-50 text-sky-900"
  }[reason.severity];
  const localizedReason = copy.reasonCodes[reason.code] ?? {
    title: reason.title,
    detail: reason.detail
  };

  return (
    <div className={`rounded-md border p-3 ${severityClass}`}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-semibold">{localizedReason.title}</p>
        <span className="text-xs font-semibold uppercase tracking-normal">
          {copy.severity[reason.severity]}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6">{localizedReason.detail}</p>
      <p className="mt-2 break-all font-mono text-xs opacity-75">{reason.code}</p>
    </div>
  );
}

function WatchlistPanel({
  watchlist,
  watchlistName,
  selectedTicker,
  locale,
  copy,
  onSelectTicker,
  onRemoveTicker
}: {
  watchlist: Watchlist | null;
  watchlistName: string;
  selectedTicker: string;
  locale: Locale;
  copy: DashboardCopy;
  onSelectTicker: (ticker: string) => void;
  onRemoveTicker: (ticker: string) => void;
}) {
  const tickers = watchlist?.tickers ?? [];

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">{copy.panels.sessionWatchlist}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {formatNumber(watchlist?.record_count, locale, copy.common.na)} {copy.common.viewed} |{" "}
            {watchlistName}
          </p>
        </div>
        <ListChecks className="text-data" size={22} aria-hidden="true" />
      </div>
      {tickers.length === 0 ? <PanelState label={copy.states.noViewedTickers} /> : null}
      {tickers.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-[620px] w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
                <th className="py-3 pr-3 font-semibold">{copy.labels.ticker}</th>
                <th className="px-3 py-3 font-semibold">{copy.labels.market}</th>
                <th className="px-3 py-3 font-semibold">{copy.labels.latest}</th>
                <th className="px-3 py-3 font-semibold">{copy.labels.trustScore}</th>
                <th className="px-3 py-3 font-semibold">{copy.labels.action}</th>
              </tr>
            </thead>
            <tbody>
              {tickers.map((ticker) => (
                <WatchlistRow
                  key={`${ticker.market}-${ticker.ticker}`}
                  ticker={ticker}
                  selected={selectedTicker === ticker.ticker}
                  copy={copy}
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
  copy,
  onSelectTicker,
  onRemoveTicker
}: {
  ticker: WatchlistTicker;
  selected: boolean;
  copy: DashboardCopy;
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
      <td className="px-3 py-3 text-slate-600">
        {copy.markets[ticker.market] ?? ticker.market.toUpperCase()}
      </td>
      <td className="px-3 py-3">
        {ticker.latest_warning ? (
          <LevelBadge level={ticker.latest_warning.warning_level} copy={copy} />
        ) : (
          <span className="inline-flex min-w-[86px] items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold uppercase tracking-normal text-slate-600">
            {copy.common.noAnalysis}
          </span>
        )}
      </td>
      <td className="px-3 py-3">
        {ticker.latest_warning ? formatPercent(ticker.latest_warning.trust_score, copy.common.na) : copy.common.na}
      </td>
      <td className="px-3 py-3">
        <button
          className="grid h-9 w-9 place-items-center rounded-md border border-line bg-white text-slate-600 hover:bg-red-50 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-data"
          type="button"
          aria-label={`${copy.common.remove} ${ticker.ticker}`}
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
  loading,
  locale,
  copy
}: {
  records: PredictionRecord[];
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  loading: boolean;
  locale: Locale;
  copy: DashboardCopy;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-normal">{copy.panels.latestWarnings}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {formatNumber(records.length, locale, copy.common.na)} {copy.common.rows}
          </p>
        </div>
        {loading ? <span className="text-sm font-medium text-data">{copy.common.loading}</span> : null}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[760px] w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-normal text-slate-500">
              <th className="py-3 pr-3 font-semibold">{copy.labels.ticker}</th>
              <th className="px-3 py-3 font-semibold">{copy.labels.level}</th>
              <th className="px-3 py-3 font-semibold">{copy.labels.calibratedRisk}</th>
              <th className="px-3 py-3 font-semibold">{copy.labels.trustScore}</th>
              <th className="px-3 py-3 font-semibold">{copy.labels.uncertainty}</th>
              <th className="px-3 py-3 font-semibold">{copy.labels.date}</th>
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
                  <LevelBadge level={record.warning_level} copy={copy} />
                </td>
                <td className="px-3 py-3 font-medium">
                  {formatPercent(record.calibrated_risk_probability, copy.common.na)}
                </td>
                <td className="px-3 py-3">{formatPercent(record.trust_score, copy.common.na)}</td>
                <td className="px-3 py-3">{formatPercent(record.uncertainty_score, copy.common.na)}</td>
                <td className="px-3 py-3 text-slate-500">{record.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LevelBadge({ level, copy }: { level: WarningLevel; copy: DashboardCopy }) {
  return (
    <span
      className={`inline-flex min-w-[86px] items-center justify-center rounded-md border px-2.5 py-1 text-xs font-semibold uppercase tracking-normal ${levelStyles[level]}`}
    >
      {copy.warningLevels[level]}
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
