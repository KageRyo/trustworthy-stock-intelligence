import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { tickerAnalysisSchema } from "./schemas";

const payloadPath = process.env.TSI_E2E_ANALYSIS_PATH;
const e2eTest = payloadPath && existsSync(payloadPath) ? it : it.skip;

describe("watchlist-to-warning API payload", () => {
  e2eTest("matches the runtime ticker analysis contract", () => {
    const payload = JSON.parse(readFileSync(payloadPath as string, "utf-8"));
    const analysis = tickerAnalysisSchema.parse(payload);
    expect(analysis.schema_version).toBe("analysis.v1");
    expect(analysis.warning.level).toBe("alert");
  });
});

