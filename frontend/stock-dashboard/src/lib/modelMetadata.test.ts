import { describe, expect, it } from "vitest";
import { resolveModelMetadata } from "./modelMetadata";

const globalModel = { model: "taiwan-model", model_bundle: "taiwan-bundle" };
const globalStatus = { data_as_of: "2026-10-15", generated_at: "2026-10-15T12:00:00Z" };

describe("displayed model provenance", () => {
  it("keeps a selected ticker's model and timestamps together across market refreshes", () => {
    const selected = {
      model: { name: "us-model", model_bundle: "us-bundle" },
      data_as_of: "2026-10-14", generated_at: "2026-10-15T06:00:00Z"
    };
    expect(resolveModelMetadata(selected, globalModel, globalStatus)).toEqual({
      modelName: "us-model", modelBundle: "us-bundle", dataAsOf: "2026-10-14",
      generatedAt: "2026-10-15T06:00:00Z"
    });
  });

  it("uses global provenance only before a ticker is selected", () => {
    expect(resolveModelMetadata(null, globalModel, globalStatus)).toEqual({
      modelName: "taiwan-model", modelBundle: "taiwan-bundle", dataAsOf: "2026-10-15",
      generatedAt: "2026-10-15T12:00:00Z"
    });
  });
});
