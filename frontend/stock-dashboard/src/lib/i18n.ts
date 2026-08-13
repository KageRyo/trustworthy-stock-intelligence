import type { WarningLevel } from "./schemas";

export type Locale = "en" | "zh-Hant";
export type ReasonSeverity = "info" | "watch" | "alert";

type TextPair = {
  title: string;
  detail: string;
};

export type DashboardCopy = {
  localeName: string;
  productName: string;
  appTitle: string;
  searchPlaceholder: string;
  searchAria: string;
  common: {
    na: string;
    search: string;
    refresh: string;
    loading: string;
    remove: string;
    rows: string;
    reasons: string;
    viewed: string;
    noAnalysis: string;
  };
  language: {
    label: string;
    english: string;
    zhHant: string;
  };
  metrics: {
    alerts: string;
    watch: string;
    avgTrust: string;
    highestRisk: string;
    lowestTrust: string;
    coverage: string;
  };
  panels: {
    tickerAnalysis: string;
    operationalStatus: string;
    noTickerSelected: string;
    calibratedRisk: string;
    trustAndModel: string;
    calibrationDrift: string;
    reasonCodes: string;
    featureAttributions: string;
    sessionWatchlist: string;
    latestWarnings: string;
    tickerTimeline: string;
  };
  labels: {
    rawRisk: string;
    calibratedRisk: string;
    alertThreshold: string;
    watchThreshold: string;
    trustScore: string;
    trustStatus: string;
    uncertainty: string;
    uncertaintyStatus: string;
    calibration: string;
    dataAsOf: string;
    generatedAt: string;
    modelBundle: string;
    ticker: string;
    market: string;
    latest: string;
    action: string;
    level: string;
    date: string;
    contribution: string;
    driftStatus: string;
    driftSignals: string;
    eventRateDelta: string;
    eceDelta: string;
    brierDelta: string;
    calibrationRows: string;
    recentRows: string;
    freshness: string;
    freshnessReason: string;
    analysisStatus: string;
    providerStatus: string;
    coverageStatus: string;
    jobStatus: string;
  };
  states: {
    loadingAnalysis: string;
    loadingHistory: string;
    noReasonCodes: string;
    noViewedTickers: string;
    noHistory: string;
    loadingProviderHealth: string;
    providerHealthUnavailable: string;
    noProviderHealth: string;
    loadingPrediction: string;
    queuedPrediction: string;
    runningPrediction: string;
    completedPrediction: string;
    failedPrediction: string;
    cancelledPrediction: string;
    unavailable: string;
  };
  errors: {
    unexpected: string;
    noMarketData: (ticker: string) => string;
    historyUnavailable: string;
    providerHealthUnavailable: string;
    predictionJobUnavailable: string;
  };
  notices: {
    watchlistJoinNotRefreshed: (ticker: string) => string;
    predictionQueued: (ticker: string) => string;
  };
  warningLevels: Record<WarningLevel, string>;
  warningSummaries: Record<WarningLevel, string>;
  trustStatuses: Record<string, string>;
  uncertaintyStatuses: Record<string, string>;
  driftStatuses: Record<string, string>;
  freshnessStatuses: Record<string, string>;
  freshnessActions: Record<string, string>;
  operational: {
    fresh: string;
    stale: string;
    unusable: string;
    healthy: string;
    degraded: string;
    unavailable: string;
    available: string;
    partial: string;
    unknown: string;
    trusted: string;
    limited: string;
    abstain: string;
    queued: string;
    running: string;
    completed: string;
    failed: string;
    cancelled: string;
  };
  trustSummaries: {
    insufficientHistory: string;
    highUncertainty: string;
    trustedForAlert: string;
    limitedTrust: string;
    calibrationDriftDetected: string;
    calibrationDriftAbstain: string;
    calibrationDriftNotEvaluated: string;
    default: string;
  };
  severity: Record<ReasonSeverity, string>;
  markets: Record<string, string>;
  chart: {
    risk: string;
    calibrated: string;
    trust: string;
    uncertainty: string;
    warningLevel: string;
  };
  attributionNote: string;
  reasonCodes: Record<string, TextPair>;
};

export const localeStorageKey = "tsi.dashboard.locale";

export const translations = {
  en: {
    localeName: "English",
    productName: "Trustworthy Stock Intelligence",
    appTitle: "Stock Risk Dashboard",
    searchPlaceholder: "Ticker or 2330",
    searchAria: "Ticker or Taiwan stock code",
    common: {
      na: "n/a",
      search: "Search",
      refresh: "Refresh",
      loading: "Loading",
      remove: "Remove",
      rows: "rows",
      reasons: "reasons",
      viewed: "viewed",
      noAnalysis: "No Analysis"
    },
    language: {
      label: "Language",
      english: "English",
      zhHant: "正體中文"
    },
    metrics: {
      alerts: "Alerts",
      watch: "Watch",
      avgTrust: "Avg Trust",
      highestRisk: "Highest Risk",
      lowestTrust: "Lowest Trust",
      coverage: "Coverage"
    },
    panels: {
      tickerAnalysis: "Ticker Analysis",
      operationalStatus: "Operational Status",
      noTickerSelected: "No ticker selected",
      calibratedRisk: "Calibrated Risk",
      trustAndModel: "Trust And Model",
      calibrationDrift: "Calibration Drift",
      reasonCodes: "Reason Codes",
      featureAttributions: "Feature Attribution",
      sessionWatchlist: "Session Watchlist",
      latestWarnings: "Latest Warnings",
      tickerTimeline: "Ticker Timeline"
    },
    labels: {
      rawRisk: "Raw Risk",
      calibratedRisk: "Calibrated Risk",
      alertThreshold: "Alert Threshold",
      watchThreshold: "Watch Threshold",
      trustScore: "Trust Score",
      trustStatus: "Trust Status",
      uncertainty: "Uncertainty",
      uncertaintyStatus: "Uncertainty Status",
      calibration: "Calibration",
      dataAsOf: "Data As Of",
      generatedAt: "Generated At",
      modelBundle: "Model Bundle",
      ticker: "Ticker",
      market: "Market",
      latest: "Latest",
      action: "Action",
      level: "Level",
      date: "Date",
      contribution: "Contribution",
      driftStatus: "Drift Status",
      driftSignals: "Signals",
      eventRateDelta: "Event-rate Δ",
      eceDelta: "ECE Δ",
      brierDelta: "Brier Δ",
      calibrationRows: "Calibration Rows",
      recentRows: "Recent Rows",
      freshness: "Data Freshness",
      freshnessReason: "Freshness reason",
      analysisStatus: "Analysis status",
      providerStatus: "Provider health",
      coverageStatus: "Coverage status",
      jobStatus: "Prediction job"
    },
    states: {
      loadingAnalysis: "Loading analysis",
      loadingHistory: "Loading warning history",
      noReasonCodes: "No reason codes",
      noViewedTickers: "No viewed tickers in this session",
      noHistory: "No historical warning records are available for this ticker.",
      loadingProviderHealth: "Loading provider health",
      providerHealthUnavailable: "Provider health is unavailable",
      noProviderHealth: "No provider observation is available for this ticker",
      loadingPrediction: "Loading prediction",
      queuedPrediction: "Prediction is queued",
      runningPrediction: "Prediction is running",
      completedPrediction: "Prediction completed",
      failedPrediction: "Prediction failed",
      cancelledPrediction: "Prediction was cancelled",
      unavailable: "Unavailable"
    },
    errors: {
      unexpected: "Unexpected error",
      noMarketData: (ticker: string) =>
        `No market data or model output could be generated for ${ticker}. Check the symbol and provider coverage.`,
      historyUnavailable: "Warning history is temporarily unavailable.",
      providerHealthUnavailable: "Provider health could not be loaded; coverage may be unknown.",
      predictionJobUnavailable: "The prediction job could not be queued."
    },
    notices: {
      watchlistJoinNotRefreshed: (ticker: string) =>
        `${ticker} was analyzed, but the watchlist join has not refreshed yet.`,
      predictionQueued: (ticker: string) =>
        `${ticker} is queued for analysis. This screen will update when the worker completes it.`
    },
    warningLevels: {
      alert: "Alert",
      watch: "Watch",
      abstain: "Abstain",
      no_alert: "No Alert"
    },
    warningSummaries: {
      alert: "High calibrated drawdown-risk signal with enough trust to issue an alert.",
      watch: "Moderate or elevated drawdown-risk signal that should remain on watch.",
      abstain: "Model uncertainty or calibration drift is too high for a confident warning decision.",
      no_alert: "No material drawdown-risk warning in the latest available data."
    },
    trustStatuses: {
      trusted_for_alert: "Trusted for alert",
      limited_trust: "Limited trust",
      unknown: "Unknown"
    },
    uncertaintyStatuses: {
      high_uncertainty: "High uncertainty",
      acceptable_uncertainty: "Acceptable uncertainty",
      unknown: "Unknown"
    },
    driftStatuses: {
      not_evaluated: "Not evaluated",
      stable: "Stable",
      degraded: "Degraded"
    },
    freshnessStatuses: {
      fresh: "Fresh",
      stale: "Stale",
      unusable: "Unusable"
    },
    freshnessActions: {
      allow: "Allowed",
      downgrade: "Downgrade confidence",
      block: "Blocked / abstain"
    },
    operational: {
      fresh: "Fresh",
      stale: "Stale",
      unusable: "Unusable",
      healthy: "Healthy",
      degraded: "Degraded",
      unavailable: "Unavailable",
      available: "Available",
      partial: "Partial",
      unknown: "Unknown",
      trusted: "Trusted",
      limited: "Limited trust",
      abstain: "Abstention",
      queued: "Queued",
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      cancelled: "Cancelled"
    },
    trustSummaries: {
      insufficientHistory:
        "The ticker has market data, but not enough labeled history for a calibrated risk prediction.",
      highUncertainty:
        "Uncertainty is above the configured threshold, so the model output should be treated cautiously.",
      trustedForAlert: "Trust score is above the configured alert threshold for this batch.",
      limitedTrust: "Trust score is below the configured alert threshold for this batch.",
      calibrationDriftDetected: "Calibration drift was detected and the trust score was reduced.",
      calibrationDriftAbstain: "Calibration drift crossed the abstention gate; treat this output as non-actionable.",
      calibrationDriftNotEvaluated: "Calibration drift was not evaluated because no later labeled window was available.",
      default: "Trust assessment is based on calibrated probability and uncertainty for this batch."
    },
    severity: {
      alert: "alert",
      watch: "watch",
      info: "info"
    },
    markets: {
      us: "US",
      taiwan: "Taiwan",
      twse: "TWSE",
      tpex: "TPEx",
      emerging: "Emerging",
      unknown: "Unknown"
    },
    chart: {
      risk: "Risk",
      calibrated: "Calibrated",
      trust: "Trust",
      uncertainty: "Uncertainty",
      warningLevel: "Warning Level"
    },
    attributionNote:
      "These are model-specific standardized log-odds contributions, not causal explanations or investment advice.",
    reasonCodes: {
      probability_above_alert_threshold: {
        title: "Risk probability above alert threshold",
        detail: "The calibrated risk probability is at or above the configured alert threshold."
      },
      probability_above_watch_threshold: {
        title: "Risk probability above watch threshold",
        detail: "The calibrated risk probability is at or above the configured watch threshold."
      },
      calibrated_probability_below_watch_threshold: {
        title: "Risk probability below watch threshold",
        detail: "The calibrated risk probability is below the configured watch threshold."
      },
      trust_above_alert_threshold: {
        title: "Trust score above alert threshold",
        detail: "The trust score is high enough to support an alert decision."
      },
      trust_below_alert_threshold: {
        title: "Trust score below alert threshold",
        detail: "The trust score is not high enough to support an alert decision."
      },
      uncertainty_above_threshold: {
        title: "Uncertainty above threshold",
        detail: "The uncertainty score is above the configured threshold."
      },
      uncertainty_below_threshold: {
        title: "Uncertainty below threshold",
        detail: "The uncertainty score is below the configured threshold."
      },
      warning_level_alert: {
        title: "Alert warning level",
        detail: "The final warning decision is alert."
      },
      warning_level_watch: {
        title: "Watch warning level",
        detail: "The final warning decision is watch."
      },
      warning_level_abstain: {
        title: "Abstain warning level",
        detail: "The final warning decision is abstain because confidence is limited."
      },
      warning_level_no_alert: {
        title: "No alert warning level",
        detail: "The final warning decision is no alert."
      },
      insufficient_history: {
        title: "Insufficient price history",
        detail: "The ticker has market data, but not enough labeled history for a calibrated risk prediction."
      }
    }
  },
  "zh-Hant": {
    localeName: "正體中文",
    productName: "可信任股票智慧",
    appTitle: "股票風險儀表板",
    searchPlaceholder: "股票代號或 2330",
    searchAria: "股票代號或台股代號",
    common: {
      na: "無資料",
      search: "搜尋",
      refresh: "更新",
      loading: "載入中",
      remove: "移除",
      rows: "筆資料",
      reasons: "個理由",
      viewed: "已看過",
      noAnalysis: "尚無分析"
    },
    language: {
      label: "語言",
      english: "English",
      zhHant: "正體中文"
    },
    metrics: {
      alerts: "警示",
      watch: "觀察",
      avgTrust: "平均信任分數",
      highestRisk: "最高風險",
      lowestTrust: "最低信任",
      coverage: "涵蓋範圍"
    },
    panels: {
      tickerAnalysis: "股票分析",
      operationalStatus: "運作狀態",
      noTickerSelected: "尚未選擇股票代號",
      calibratedRisk: "校準後風險",
      trustAndModel: "信任與模型",
      calibrationDrift: "校準漂移",
      reasonCodes: "原因代碼",
      featureAttributions: "特徵貢獻",
      sessionWatchlist: "本次瀏覽觀察清單",
      latestWarnings: "最新風險訊號",
      tickerTimeline: "股票風險時間線"
    },
    labels: {
      rawRisk: "原始風險",
      calibratedRisk: "校準後風險",
      alertThreshold: "警示門檻",
      watchThreshold: "觀察門檻",
      trustScore: "信任分數",
      trustStatus: "信任狀態",
      uncertainty: "不確定性",
      uncertaintyStatus: "不確定性狀態",
      calibration: "校準方式",
      dataAsOf: "資料截至",
      generatedAt: "產生時間",
      modelBundle: "模型套件",
      ticker: "股票代號",
      market: "市場",
      latest: "最新",
      action: "操作",
      level: "等級",
      date: "日期",
      contribution: "貢獻",
      driftStatus: "漂移狀態",
      driftSignals: "訊號",
      eventRateDelta: "事件率變化 Δ",
      eceDelta: "ECE 變化 Δ",
      brierDelta: "Brier 變化 Δ",
      calibrationRows: "校準資料列數",
      recentRows: "近期資料列數",
      freshness: "資料新鮮度",
      freshnessReason: "新鮮度原因",
      analysisStatus: "分析狀態",
      providerStatus: "資料來源健康度",
      coverageStatus: "涵蓋狀態",
      jobStatus: "預測工作"
    },
    states: {
      loadingAnalysis: "正在載入分析",
      loadingHistory: "正在載入警示歷史",
      noReasonCodes: "沒有原因代碼",
      noViewedTickers: "本次瀏覽尚未查看任何股票",
      noHistory: "此股票目前沒有可用的歷史警示資料。",
      loadingProviderHealth: "正在載入資料來源健康度",
      providerHealthUnavailable: "資料來源健康度目前無法取得",
      noProviderHealth: "此股票目前沒有資料來源觀測紀錄",
      loadingPrediction: "正在載入預測",
      queuedPrediction: "預測已排入佇列",
      runningPrediction: "預測執行中",
      completedPrediction: "預測已完成",
      failedPrediction: "預測失敗",
      cancelledPrediction: "預測已取消",
      unavailable: "不可用"
    },
    errors: {
      unexpected: "發生未預期錯誤",
      noMarketData: (ticker: string) =>
        `無法為 ${ticker} 產生市場資料或模型輸出。請確認代號與資料來源涵蓋範圍。`,
      historyUnavailable: "警示歷史暫時無法取得。",
      providerHealthUnavailable: "無法載入資料來源健康度；涵蓋狀態可能未知。",
      predictionJobUnavailable: "預測工作無法排入佇列。"
    },
    notices: {
      watchlistJoinNotRefreshed: (ticker: string) =>
        `${ticker} 已完成分析，但觀察清單關聯尚未更新。`,
      predictionQueued: (ticker: string) =>
        `${ticker} 已排入分析佇列；工作完成後此畫面會自動更新。`
    },
    warningLevels: {
      alert: "警示",
      watch: "觀察",
      abstain: "暫不判斷",
      no_alert: "無警示"
    },
    warningSummaries: {
      alert: "校準後回撤風險偏高，且信任條件足以發出警示。",
      watch: "回撤風險中等或偏高，建議維持觀察。",
      abstain: "模型不確定性或校準漂移過高，暫不給出高信心警示。",
      no_alert: "最新可用資料未顯示明顯回撤風險警示。"
    },
    trustStatuses: {
      trusted_for_alert: "可支援警示",
      limited_trust: "信任有限",
      unknown: "未知"
    },
    uncertaintyStatuses: {
      high_uncertainty: "高不確定性",
      acceptable_uncertainty: "可接受不確定性",
      unknown: "未知"
    },
    driftStatuses: {
      not_evaluated: "尚未評估",
      stable: "穩定",
      degraded: "劣化"
    },
    freshnessStatuses: {
      fresh: "新鮮",
      stale: "過期",
      unusable: "不可用"
    },
    freshnessActions: {
      allow: "可使用",
      downgrade: "降低信心",
      block: "阻擋／暫不判斷"
    },
    operational: {
      fresh: "新鮮",
      stale: "過期",
      unusable: "不可用",
      healthy: "健康",
      degraded: "劣化",
      unavailable: "不可用",
      available: "可用",
      partial: "部分可用",
      unknown: "未知",
      trusted: "可支援警示",
      limited: "信任有限",
      abstain: "暫不判斷",
      queued: "已排隊",
      running: "執行中",
      completed: "已完成",
      failed: "失敗",
      cancelled: "已取消"
    },
    trustSummaries: {
      insufficientHistory: "此股票有市場資料，但標註歷史不足，無法產生校準後風險預測。",
      highUncertainty: "不確定性高於設定門檻，模型輸出應保守解讀。",
      trustedForAlert: "此批次的信任分數高於警示門檻。",
      limitedTrust: "此批次的信任分數低於警示門檻。",
      calibrationDriftDetected: "偵測到校準漂移，信任分數已降低。",
      calibrationDriftAbstain: "校準漂移跨越暫不判斷門檻，這項輸出不可直接採取行動。",
      calibrationDriftNotEvaluated: "沒有較晚的標註資料窗，因此尚未評估校準漂移。",
      default: "信任評估基於校準後機率與不確定性。"
    },
    severity: {
      alert: "警示",
      watch: "觀察",
      info: "資訊"
    },
    markets: {
      us: "美股",
      taiwan: "台股",
      twse: "上市",
      tpex: "上櫃",
      emerging: "興櫃",
      unknown: "未知"
    },
    chart: {
      risk: "風險",
      calibrated: "校準後",
      trust: "信任",
      uncertainty: "不確定性",
      warningLevel: "警示等級"
    },
    attributionNote: "這些是模型特定的標準化 log-odds 貢獻，不是因果解釋，也不是投資建議。",
    reasonCodes: {
      probability_above_alert_threshold: {
        title: "風險機率高於警示門檻",
        detail: "校準後風險機率已達或高於設定的警示門檻。"
      },
      probability_above_watch_threshold: {
        title: "風險機率高於觀察門檻",
        detail: "校準後風險機率已達或高於設定的觀察門檻。"
      },
      calibrated_probability_below_watch_threshold: {
        title: "風險機率低於觀察門檻",
        detail: "校準後風險機率低於設定的觀察門檻。"
      },
      trust_above_alert_threshold: {
        title: "信任分數高於警示門檻",
        detail: "信任分數足以支援警示判斷。"
      },
      trust_below_alert_threshold: {
        title: "信任分數低於警示門檻",
        detail: "信任分數不足以支援高信心警示。"
      },
      uncertainty_above_threshold: {
        title: "不確定性高於門檻",
        detail: "不確定性分數高於設定門檻。"
      },
      uncertainty_below_threshold: {
        title: "不確定性低於門檻",
        detail: "不確定性分數低於設定門檻。"
      },
      warning_level_alert: {
        title: "最終等級為警示",
        detail: "模型最終決策為警示。"
      },
      warning_level_watch: {
        title: "最終等級為觀察",
        detail: "模型最終決策為觀察。"
      },
      warning_level_abstain: {
        title: "最終等級為暫不判斷",
        detail: "因信心有限，模型最終決策為暫不判斷。"
      },
      warning_level_no_alert: {
        title: "最終等級為無警示",
        detail: "模型最終決策為無警示。"
      },
      insufficient_history: {
        title: "價格歷史不足",
        detail: "此股票有市場資料，但標註歷史不足，無法產生校準後風險預測。"
      }
    }
  }
} satisfies Record<Locale, DashboardCopy>;

export function readStoredLocale(): Locale {
  if (typeof window === "undefined") {
    return detectLocale();
  }
  try {
    const stored = window.localStorage.getItem(localeStorageKey);
    if (stored === "en" || stored === "zh-Hant") {
      return stored;
    }
  } catch {
    return detectLocale(window.navigator.language);
  }
  return detectLocale(window.navigator.language);
}

export function storeLocale(locale: Locale): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(localeStorageKey, locale);
  } catch {
    // Language selection is a preference, not required application state.
  }
}

export function detectLocale(language = "en"): Locale {
  return language.toLowerCase().startsWith("zh") ? "zh-Hant" : "en";
}

export function numberLocale(locale: Locale): string {
  return locale === "zh-Hant" ? "zh-TW" : "en-US";
}
