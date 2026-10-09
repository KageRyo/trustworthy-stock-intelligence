import { describe, expect, it } from "vitest";
import { detectLocale, translations } from "./i18n";

describe("dashboard i18n", () => {
  it("detects Chinese browser languages as 正體中文 locale", () => {
    expect(detectLocale("zh-TW")).toBe("zh-Hant");
    expect(detectLocale("zh-HK")).toBe("zh-Hant");
    expect(detectLocale("en-US")).toBe("en");
  });

  it("uses 正體中文 wording for the Chinese language option", () => {
    const copy = translations["zh-Hant"];
    const disallowedLabel = "\u7e41\u9ad4";

    expect(copy.localeName).toBe("正體中文");
    expect(copy.language.zhHant).toBe("正體中文");
    expect(JSON.stringify(copy)).not.toContain(disallowedLabel);
  });

  it("localizes trustworthy AI reason codes", () => {
    expect(translations.en.reasonCodes.insufficient_history.title).toBe(
      "Insufficient price history"
    );
    expect(translations["zh-Hant"].reasonCodes.insufficient_history.title).toBe("價格歷史不足");
  });
});

describe("reliability reason codes", () => {
  const codes = [
    "calibration_slope_nonpositive",
    "single_ticker_model",
    "model_bundle_stale",
    "ensemble_disagreement_high",
    "input_out_of_distribution",
    "limited_data_quality",
    "stale_ticker_data",
    "reliability_unavailable",
    "conformal_set_ambiguous",
    "conformal_set_drawdown_only",
    "conformal_set_no_drawdown_only",
    "conformal_set_empty",
    "conformal_set_unavailable"
  ] as const;

  it("localizes every reliability reason code in both locales", () => {
    for (const code of codes) {
      expect(translations.en.reasonCodes[code].title).toBeTruthy();
      expect(translations["zh-Hant"].reasonCodes[code].title).toBeTruthy();
    }
  });
});
