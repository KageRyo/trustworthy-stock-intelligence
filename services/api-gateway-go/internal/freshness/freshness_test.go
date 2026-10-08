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

func TestDailyCutoffIsTheMarketSessionClose(t *testing.T) {
	cases := []struct {
		name        string
		dataAsOf    string
		evaluatedAt string
		market      string
		reason      string
		ageSeconds  float64
	}{
		// 13:30 Taipei is 05:30 UTC; 19:00 Taipei on the same day is fresh, not future.
		{"taiwan same evening", "2026-10-08", "2026-10-08T11:00:00Z", "twse", "freshness_fresh", 5.5 * 3600},
		// 10:00 Taipei is before the close, so today's daily bar is not complete yet.
		{"taiwan intraday partial bar", "2026-10-08", "2026-10-08T02:00:00Z", "twse", "freshness_future_data_as_of", 0},
		{"emerging closes at 15:00", "2026-10-08", "2026-10-08T07:30:00Z", "emerging", "freshness_fresh", 1800},
		// 16:00 New York in October (EDT) is 20:00 UTC.
		{"us after the close", "2026-10-07", "2026-10-07T21:00:00Z", "us", "freshness_fresh", 3600},
		{"us before the close", "2026-10-07", "2026-10-07T19:00:00Z", "us", "freshness_future_data_as_of", 0},
		{"unknown market uses UTC midnight", "2026-10-07", "2026-10-07T06:00:00Z", "unknown", "freshness_fresh", 6 * 3600},
	}
	for _, testCase := range cases {
		assessment := Assess(testCase.dataAsOf, testCase.evaluatedAt, testCase.market, "1d")
		if assessment.ReasonCode != testCase.reason {
			t.Fatalf("%s: reason = %q, want %q", testCase.name, assessment.ReasonCode, testCase.reason)
		}
		if assessment.AgeSeconds == nil || *assessment.AgeSeconds != testCase.ageSeconds {
			t.Fatalf("%s: age = %v, want %v", testCase.name, assessment.AgeSeconds, testCase.ageSeconds)
		}
	}
}
