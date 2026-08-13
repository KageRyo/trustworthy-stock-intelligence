package freshness

import "testing"

func TestAssessFreshCutoff(t *testing.T) {
	assessment := Assess("2026-06-19T00:55:00Z", "2026-06-19T01:00:00Z", "us", "5m")

	if assessment.State != StateFresh || assessment.Action != ActionAllow {
		t.Fatalf("unexpected fresh assessment: %+v", assessment)
	}
	if assessment.ReasonCode != "freshness_fresh" || assessment.AgeSeconds == nil || *assessment.AgeSeconds != 300 {
		t.Fatalf("unexpected fresh metadata: %+v", assessment)
	}
}

func TestAssessStaleCutoffDowngradesToAbstainOverride(t *testing.T) {
	assessment := Assess("2026-06-19T00:00:00Z", "2026-06-19T00:30:00Z", "twse", "5m")

	if assessment.State != StateStale || assessment.Action != ActionDowngrade {
		t.Fatalf("unexpected stale assessment: %+v", assessment)
	}
	if assessment.WarningLevelOverride != "abstain" || assessment.ReasonCode != "freshness_stale" {
		t.Fatalf("unexpected stale override: %+v", assessment)
	}
}

func TestAssessMissingFutureAndUnusableCutoffsBlock(t *testing.T) {
	missing := Assess("", "2026-06-19T00:00:00Z", "us", "1d")
	future := Assess("2026-06-20T00:00:00Z", "2026-06-19T00:00:00Z", "us", "1d")
	old := Assess("2026-06-01", "2026-06-19T00:00:00Z", "us", "1d")

	if missing.ReasonCode != "freshness_missing_data_as_of" || missing.Action != ActionBlock {
		t.Fatalf("unexpected missing assessment: %+v", missing)
	}
	if future.ReasonCode != "freshness_future_data_as_of" || future.Action != ActionBlock {
		t.Fatalf("unexpected future assessment: %+v", future)
	}
	if old.State != StateUnusable || old.ReasonCode != "freshness_unusable" {
		t.Fatalf("unexpected old assessment: %+v", old)
	}
}
