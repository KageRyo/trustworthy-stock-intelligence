package apihttp

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/freshness"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

const (
	watchlistSchemaVersion           = "watchlist.v1"
	watchlistAddRequestSchemaVersion = "watchlist_add.v1"
)

type WatchlistResponse struct {
	SchemaVersion string                   `json:"schema_version"`
	Name          string                   `json:"name"`
	RecordCount   int                      `json:"record_count"`
	UpdatedAt     string                   `json:"updated_at"`
	Tickers       []WatchlistTickerSummary `json:"tickers"`
}

type WatchlistTickerSummary struct {
	Ticker           string                  `json:"ticker"`
	QuerySymbol      string                  `json:"query_symbol"`
	Market           string                  `json:"market"`
	AddedAt          string                  `json:"added_at"`
	Notes            string                  `json:"notes"`
	HasLatestWarning bool                    `json:"has_latest_warning"`
	LatestWarning    *WatchlistLatestWarning `json:"latest_warning,omitempty"`
}

type WatchlistLatestWarning struct {
	Date                      string  `json:"date"`
	DataAsOf                  string  `json:"data_as_of"`
	WarningLevel              string  `json:"warning_level"`
	CalibratedRiskProbability float64 `json:"calibrated_risk_probability"`
	UncertaintyScore          float64 `json:"uncertainty_score"`
	TrustScore                float64 `json:"trust_score"`
	AlertThreshold            float64 `json:"alert_threshold"`
	FreshnessState            string  `json:"freshness_state"`
	FreshnessAction           string  `json:"freshness_action"`
}

type WatchlistAddTickerRequest struct {
	SchemaVersion string `json:"schema_version"`
	Ticker        string `json:"ticker"`
	Market        string `json:"market"`
	Notes         string `json:"notes"`
}

func (h *Handlers) Watchlist(response http.ResponseWriter, request *http.Request) {
	if h.watchlist == nil {
		writeError(
			response,
			http.StatusServiceUnavailable,
			newHTTPError("watchlist_store_unavailable", "watchlist store is unavailable"),
		)
		return
	}
	payload, err := h.loadWatchlistResponse(request.PathValue("name"), request)
	if err != nil {
		writeError(response, http.StatusInternalServerError, err)
		return
	}
	writeJSON(response, http.StatusOK, payload)
}

func (h *Handlers) AddWatchlistTicker(response http.ResponseWriter, request *http.Request) {
	if h.watchlist == nil {
		writeError(
			response,
			http.StatusServiceUnavailable,
			newHTTPError("watchlist_store_unavailable", "watchlist store is unavailable"),
		)
		return
	}
	var payload WatchlistAddTickerRequest
	decoder := json.NewDecoder(request.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&payload); err != nil {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_request", "invalid request JSON"))
		return
	}
	if strings.TrimSpace(payload.SchemaVersion) != watchlistAddRequestSchemaVersion {
		writeError(
			response,
			http.StatusBadRequest,
			newHTTPError("invalid_schema_version", "schema_version must be watchlist_add.v1"),
		)
		return
	}
	if _, err := h.watchlist.AddTicker(request.Context(), request.PathValue("name"), watchlist.AddTickerInput{
		Ticker: payload.Ticker,
		Market: watchlist.Market(payload.Market),
		Notes:  payload.Notes,
	}); err != nil {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_ticker", err.Error()))
		return
	}
	watchlistResponse, err := h.loadWatchlistResponse(request.PathValue("name"), request)
	if err != nil {
		writeError(response, http.StatusInternalServerError, err)
		return
	}
	writeJSON(response, http.StatusCreated, watchlistResponse)
}

func (h *Handlers) RemoveWatchlistTicker(response http.ResponseWriter, request *http.Request) {
	if h.watchlist == nil {
		writeError(
			response,
			http.StatusServiceUnavailable,
			newHTTPError("watchlist_store_unavailable", "watchlist store is unavailable"),
		)
		return
	}
	removed, err := h.watchlist.RemoveTicker(
		request.Context(),
		request.PathValue("name"),
		request.PathValue("ticker"),
	)
	if err != nil {
		writeError(response, http.StatusInternalServerError, err)
		return
	}
	if !removed {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}
	watchlistResponse, err := h.loadWatchlistResponse(request.PathValue("name"), request)
	if err != nil {
		writeError(response, http.StatusInternalServerError, err)
		return
	}
	writeJSON(response, http.StatusOK, watchlistResponse)
}

func (h *Handlers) loadWatchlistResponse(name string, request *http.Request) (WatchlistResponse, error) {
	h.refreshStore()
	list, err := h.watchlist.List(request.Context(), name)
	if err != nil {
		return WatchlistResponse{}, err
	}
	tickers := make([]WatchlistTickerSummary, 0, len(list.Tickers))
	for _, ticker := range list.Tickers {
		summary := WatchlistTickerSummary{
			Ticker:      ticker.Ticker,
			QuerySymbol: ticker.QuerySymbol,
			Market:      ticker.Market,
			AddedAt:     ticker.AddedAt,
			Notes:       ticker.Notes,
		}
		if record, ok := h.store.FindTicker(ticker.Ticker); ok {
			freshnessAssessment := freshness.Assess(
				record.DataAsOf,
				"",
				inferTickerMarket(record.Ticker),
				"1d",
			)
			summary.HasLatestWarning = true
			summary.LatestWarning = &WatchlistLatestWarning{
				Date:                      record.Date,
				DataAsOf:                  record.DataAsOf,
				WarningLevel:              record.WarningLevel,
				CalibratedRiskProbability: record.CalibratedRiskProbability,
				UncertaintyScore:          record.UncertaintyScore,
				TrustScore:                record.TrustScore,
				AlertThreshold:            record.AlertThreshold,
				FreshnessState:            freshnessAssessment.State,
				FreshnessAction:           freshnessAssessment.Action,
			}
		}
		tickers = append(tickers, summary)
	}
	return WatchlistResponse{
		SchemaVersion: watchlistSchemaVersion,
		Name:          list.Name,
		RecordCount:   len(tickers),
		UpdatedAt:     list.UpdatedAt,
		Tickers:       tickers,
	}, nil
}
