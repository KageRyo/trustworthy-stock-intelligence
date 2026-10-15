import type { APIStatus, CurrentModel, TickerAnalysis } from "./schemas";

export function resolveModelMetadata(
  analysis: Pick<TickerAnalysis, "model" | "data_as_of" | "generated_at"> | null,
  model: Pick<CurrentModel, "model" | "model_bundle"> | null,
  status: Pick<APIStatus, "data_as_of" | "generated_at"> | null
) {
  if (analysis) {
    return {
      modelName: analysis.model.name,
      modelBundle: analysis.model.model_bundle,
      dataAsOf: analysis.data_as_of,
      generatedAt: analysis.generated_at
    };
  }
  return {
    modelName: model?.model,
    modelBundle: model?.model_bundle,
    dataAsOf: status?.data_as_of,
    generatedAt: status?.generated_at
  };
}
