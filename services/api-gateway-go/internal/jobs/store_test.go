package jobs

import "testing"

func TestNormalizeCreateRequestDefaultsAndNormalizes(t *testing.T) {
	request, err := normalizeCreateRequest(CreateRequest{Ticker: " nvda "})
	if err != nil {
		t.Fatalf("normalizeCreateRequest returned error: %v", err)
	}
	if request.Ticker != "NVDA" || request.Market != "auto" || request.FeatureInterval != "1d" {
		t.Fatalf("unexpected defaults: %+v", request)
	}
	if request.MaxAttempts != 3 || request.IdempotencyKey == "" {
		t.Fatalf("unexpected retry/idempotency defaults: %+v", request)
	}
}

func TestNormalizeCreateRequestRejectsInvalidValues(t *testing.T) {
	checks := []CreateRequest{
		{Ticker: ""},
		{Ticker: "NVDA", Market: "mars"},
		{Ticker: "NVDA", FeatureInterval: "15m"},
		{Ticker: "NVDA", MaxAttempts: 9},
	}
	for _, request := range checks {
		if _, err := normalizeCreateRequest(request); err == nil {
			t.Fatalf("normalizeCreateRequest(%+v) unexpectedly succeeded", request)
		}
	}
}
