import { describe, expect, it } from "vitest";
import { formatAlertPolicy } from "./alertPolicy";
import { translations } from "./i18n";

describe("formatAlertPolicy", () => {
  it("describes alert-rate policies as calibration-window risk percentiles", () => {
    expect(formatAlertPolicy("alert_rate:0.05", true, translations.en)).toBe(
      "Top 5% of calibration-window risk"
    );
    expect(formatAlertPolicy("alert_rate:0.2", true, translations["zh-Hant"])).toBe(
      "校準窗風險前 20%"
    );
  });

  it("describes precision targets, F1, and ratio policies", () => {
    expect(formatAlertPolicy("target_precision:0.25", true, translations.en)).toBe(
      "Precision target 25%"
    );
    expect(formatAlertPolicy("objective:f1", true, translations["zh-Hant"])).toBe("F1 最佳化");
    expect(formatAlertPolicy("f1", true, translations.en)).toBe("F1-optimized");
    expect(formatAlertPolicy("ratio:0.8", true, translations.en)).toBe("80% of alert threshold");
  });

  it("flags unmet targets and falls back to the raw policy", () => {
    expect(formatAlertPolicy("target_precision:0.3", false, translations["zh-Hant"])).toBe(
      "精確度目標 30%（未達目標）"
    );
    expect(formatAlertPolicy("custom:1", true, translations.en)).toBe("custom:1");
  });

  it("flags noisy thresholds from small calibration samples", () => {
    expect(formatAlertPolicy("alert_rate:0.05", true, translations["zh-Hant"], true)).toBe(
      "校準窗風險前 5%（校準樣本少）"
    );
  });
});
