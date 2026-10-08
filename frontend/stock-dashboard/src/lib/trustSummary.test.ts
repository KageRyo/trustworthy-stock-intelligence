import { describe, expect, it } from "vitest";
import { freshnessReasonCodes, translations, trustSummaryCodes } from "./i18n";
import { localizedFreshnessMessage, localizedTrustSummary } from "./trustSummary";

describe("localizedTrustSummary", () => {
  it("translates the API summary code", () => {
    const trust = { summary_code: "limited_data_quality", summary: "English text" };

    expect(localizedTrustSummary(trust, translations["zh-Hant"])).toBe(
      translations["zh-Hant"].trustSummaries.limited_data_quality
    );
    expect(localizedTrustSummary(trust, translations.en)).toBe(
      translations.en.trustSummaries.limited_data_quality
    );
  });

  it("falls back to the API summary for unknown or inherited codes", () => {
    expect(
      localizedTrustSummary({ summary_code: "new_code", summary: "From API" }, translations.en)
    ).toBe("From API");
    expect(
      localizedTrustSummary({ summary_code: "toString", summary: "From API" }, translations.en)
    ).toBe("From API");
  });

  it("has wording for every summary code in both locales", () => {
    for (const copy of Object.values(translations)) {
      for (const code of trustSummaryCodes) {
        expect(copy.trustSummaries[code]).toBeTruthy();
      }
    }
  });
});

describe("localizedFreshnessMessage", () => {
  it("translates freshness reason codes", () => {
    expect(
      localizedFreshnessMessage(
        { reason_code: "freshness_stale", message: "English text" },
        translations["zh-Hant"]
      )
    ).toBe(translations["zh-Hant"].freshnessMessages.freshness_stale);
  });

  it("falls back to the API message for unknown codes", () => {
    expect(
      localizedFreshnessMessage({ reason_code: "freshness_new", message: "From API" }, translations.en)
    ).toBe("From API");
  });

  it("has wording for every freshness reason code in both locales", () => {
    for (const copy of Object.values(translations)) {
      for (const code of freshnessReasonCodes) {
        expect(copy.freshnessMessages[code]).toBeTruthy();
      }
    }
  });
});
