import type { DashboardCopy } from "./i18n";

type CodedSummary = { summary_code: string; summary: string };
type FreshnessMessage = { reason_code: string; message: string };

function lookup(messages: Record<string, string>, code: string): string | undefined {
  return Object.hasOwn(messages, code) ? messages[code] : undefined;
}

/** Localize the API trust summary by its code, falling back to the API's English text. */
export function localizedTrustSummary(trust: CodedSummary, copy: DashboardCopy): string {
  return lookup(copy.trustSummaries, trust.summary_code) ?? trust.summary;
}

/** Localize a freshness assessment by its reason code, falling back to the API's message. */
export function localizedFreshnessMessage(freshness: FreshnessMessage, copy: DashboardCopy): string {
  return lookup(copy.freshnessMessages, freshness.reason_code) ?? freshness.message;
}
