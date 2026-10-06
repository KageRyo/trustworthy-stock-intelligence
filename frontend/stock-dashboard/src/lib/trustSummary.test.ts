import { describe, expect, it } from "vitest";
import { translations } from "./i18n";
import { localizedTrustSummary } from "./trustSummary";

function reasons(...codes: string[]) {
  return { reasons: codes.map((code) => ({ code })) };
}

describe("localizedTrustSummary", () => {
  it("prioritizes calibration drift over data quality", () => {
    expect(
      localizedTrustSummary(
        reasons("limited_data_quality", "calibration_drift_detected"),
        translations.en
      )
    ).toBe(translations.en.trustSummaries.calibrationDriftDetected);
  });

  it("explains limited data quality before alert trust", () => {
    expect(
      localizedTrustSummary(
        reasons("trust_above_alert_threshold", "stale_ticker_data"),
        translations["zh-Hant"]
      )
    ).toBe(translations["zh-Hant"].trustSummaries.limitedDataQuality);
  });

  it("explains unavailable reliability signals", () => {
    expect(localizedTrustSummary(reasons("reliability_unavailable"), translations.en)).toBe(
      translations.en.trustSummaries.reliabilityUnavailable
    );
  });

  it("falls back to the default summary", () => {
    expect(localizedTrustSummary(reasons(), translations.en)).toBe(
      translations.en.trustSummaries.default
    );
  });
});
