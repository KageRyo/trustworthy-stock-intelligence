package apihttp

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"testing"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

type fakeWarningTransitionStore struct {
	records []warnings.WarningTransitionRecord
	err     error
}

func (s fakeWarningTransitionStore) Transitions(
	context.Context,
	string,
	int,
) ([]warnings.WarningTransitionRecord, error) {
	return s.records, s.err
}

func TestTickerWarningTransitionsReturnsTypedRecords(t *testing.T) {
	handlers := NewHandlers(mustFileStore(t))
	handlers.SetWarningTransitionStore(fakeWarningTransitionStore{
		records: []warnings.WarningTransitionRecord{{
			SchemaVersion:        "warning_transition.v1",
			ID:                   "transition-1",
			Ticker:               "NVDA",
			TransitionType:       "new_alert",
			CurrentWarningLevel:  "alert",
			CurrentRunID:         "run-2",
			CurrentBatchID:        "batch-2",
			DetectedAt:           "2026-08-13T02:00:00Z",
			DeduplicationKey:     "NVDA:run-2:new_alert",
		}},
	})
	response := getJSON(t, NewRouter(handlers), "/api/v1/analysis/NVDA/transitions?limit=10")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200: %s", response.Code, response.Body.String())
	}
	var payload WarningTransitionsResponse
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode transitions response: %v", err)
	}
	if payload.SchemaVersion != "warning_transition.v1" || payload.RecordCount != 1 {
		t.Fatalf("unexpected transitions response: %+v", payload)
	}
	if payload.Transitions[0].TransitionType != "new_alert" {
		t.Fatalf("unexpected transition: %+v", payload.Transitions[0])
	}
}

func TestTickerWarningTransitionsReturnsTypedStoreError(t *testing.T) {
	handlers := NewHandlers(mustFileStore(t))
	handlers.SetWarningTransitionStore(fakeWarningTransitionStore{err: errors.New("database unavailable")})
	response := getJSON(t, NewRouter(handlers), "/api/v1/analysis/NVDA/transitions")
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", response.Code)
	}
}

func TestTickerWarningTransitionsRequiresStore(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/analysis/NVDA/transitions")
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", response.Code)
	}
}
