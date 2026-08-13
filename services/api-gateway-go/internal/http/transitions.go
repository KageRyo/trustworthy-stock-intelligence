package apihttp

import (
	"net/http"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

type WarningTransitionsResponse struct {
	SchemaVersion string                              `json:"schema_version"`
	Ticker        string                              `json:"ticker"`
	RecordCount   int                                 `json:"record_count"`
	Transitions   []warnings.WarningTransitionRecord `json:"transitions"`
}

func (h *Handlers) TickerWarningTransitions(response http.ResponseWriter, request *http.Request) {
	if h.transitions == nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"warning_transition_store_unavailable",
			"warning transition store is unavailable",
		))
		return
	}
	ticker := strings.TrimPrefix(request.URL.Path, "/api/v1/analysis/")
	ticker = strings.TrimSuffix(ticker, "/transitions")
	ticker = strings.TrimSpace(ticker)
	if ticker == "" || strings.Contains(ticker, "/") {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_ticker", "ticker must not be empty"))
		return
	}
	limit, err := parseHistoryLimit(request)
	if err != nil {
		writeError(response, http.StatusBadRequest, err)
		return
	}
	transitions, err := h.transitions.Transitions(request.Context(), ticker, limit)
	if err != nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"warning_transition_unavailable",
			"warning transitions could not be read",
		))
		return
	}
	if transitions == nil {
		transitions = []warnings.WarningTransitionRecord{}
	}
	writeJSON(response, http.StatusOK, WarningTransitionsResponse{
		SchemaVersion: "warning_transition.v1",
		Ticker:        ticker,
		RecordCount:   len(transitions),
		Transitions:   transitions,
	})
}
