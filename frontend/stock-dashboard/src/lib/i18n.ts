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
    noTickerSelected: string;
    calibratedRisk: string;
    trustAndModel: string;
    reasonCodes: string;
    sessionWatchlist: string;
    latestWarnings: string;
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
  };
  states: {
    loadingAnalysis: string;
    noReasonCodes: string;
    noViewedTickers: string;
  };
  errors: {
    unexpected: string;
    noMarketData: (ticker: string) => string;
  };
  notices: {
    watchlistJoinNotRefreshed: (ticker: string) => string;
  };
  warningLevels: Record<WarningLevel, string>;
  warningSummaries: Record<WarningLevel, string>;
  trustStatuses: Record<string, string>;
  uncertaintyStatuses: Record<string, string>;
  trustSummaries: {
    insufficientHistory: string;
    highUncertainty: string;
    trustedForAlert: string;
    limitedTrust: string;
    default: string;
  };
  severity: Record<ReasonSeverity, string>;
  markets: Record<string, string>;
  chart: {
    risk: string;
    calibrated: string;
    trust: string;
    uncertainty: string;
  };
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
      noTickerSelected: "No ticker selected",
      calibratedRisk: "Calibrated Risk",
      trustAndModel: "Trust And Model",
      reasonCodes: "Reason Codes",
      sessionWatchlist: "Session Watchlist",
      latestWarnings: "Latest Warnings"
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
      date: "Date"
    },
    states: {
      loadingAnalysis: "Loading analysis",
      noReasonCodes: "No reason codes",
      noViewedTickers: "No viewed tickers in this session"
    },
    errors: {
      unexpected: "Unexpected error",
      noMarketData: (ticker: string) =>
        `No market data or model output could be generated for ${ticker}. Check the symbol and provider coverage.`
    },
    notices: {
      watchlistJoinNotRefreshed: (ticker: string) =>
        `${ticker} was analyzed, but the watchlist join has not refreshed yet.`
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
      abstain: "Model uncertainty is too high for a confident warning decision.",
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
    trustSummaries: {
      insufficientHistory:
        "The ticker has market data, but not enough labeled history for a calibrated risk prediction.",
      highUncertainty:
        "Uncertainty is above the configured threshold, so the model output should be treated cautiously.",
      trustedForAlert: "Trust score is above the configured alert threshold for this batch.",
      limitedTrust: "Trust score is below the configured alert threshold for this batch.",
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
      uncertainty: "Uncertainty"
    },
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
      noTickerSelected: "尚未選擇股票代號",
      calibratedRisk: "校準後風險",
      trustAndModel: "信任與模型",
      reasonCodes: "原因代碼",
      sessionWatchlist: "本次瀏覽觀察清單",
      latestWarnings: "最新風險訊號"
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
      date: "日期"
    },
    states: {
      loadingAnalysis: "正在載入分析",
      noReasonCodes: "沒有原因代碼",
      noViewedTickers: "本次瀏覽尚未查看任何股票"
    },
    errors: {
      unexpected: "發生未預期錯誤",
      noMarketData: (ticker: string) =>
        `無法為 ${ticker} 產生市場資料或模型輸出。請確認代號與資料來源涵蓋範圍。`
    },
    notices: {
      watchlistJoinNotRefreshed: (ticker: string) =>
        `${ticker} 已完成分析，但觀察清單關聯尚未更新。`
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
      abstain: "模型不確定性過高，暫不給出高信心警示。",
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
    trustSummaries: {
      insufficientHistory: "此股票有市場資料，但標註歷史不足，無法產生校準後風險預測。",
      highUncertainty: "不確定性高於設定門檻，模型輸出應保守解讀。",
      trustedForAlert: "此批次的信任分數高於警示門檻。",
      limitedTrust: "此批次的信任分數低於警示門檻。",
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
      uncertainty: "不確定性"
    },
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
