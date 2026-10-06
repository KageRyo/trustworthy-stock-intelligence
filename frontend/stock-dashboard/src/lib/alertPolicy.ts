import type { DashboardCopy } from "./i18n";

function percent(value: string): string | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return `${Math.round(parsed * 1000) / 10}%`;
}

export function formatAlertPolicy(policy: string, targetMet: boolean, copy: DashboardCopy): string {
  const [kind, target = ""] = policy.split(":", 2);
  const value = percent(target);
  let text: string;
  if (kind === "alert_rate" && value) {
    text = copy.alertPolicies.alertRate.replace("{value}", value);
  } else if (kind === "target_precision" && value) {
    text = copy.alertPolicies.targetPrecision.replace("{value}", value);
  } else if (kind === "ratio" && value) {
    text = copy.alertPolicies.ratio.replace("{value}", value);
  } else if (kind === "f1" || (kind === "objective" && target === "f1")) {
    text = copy.alertPolicies.f1;
  } else {
    return policy;
  }
  return targetMet ? text : `${text}${copy.alertPolicies.targetNotMet}`;
}
