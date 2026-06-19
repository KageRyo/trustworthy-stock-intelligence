package apihttp

import (
	"sort"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

const tickerListSchemaVersion = "ticker_list.v1"

type TickerListResponse struct {
	SchemaVersion string          `json:"schema_version"`
	RunID         string          `json:"run_id"`
	DataAsOf      string          `json:"data_as_of"`
	GeneratedAt   string          `json:"generated_at"`
	RecordCount   int             `json:"record_count"`
	Tickers       []TickerSummary `json:"tickers"`
}

type TickerSummary struct {
	Ticker                    string  `json:"ticker"`
	Market                    string  `json:"market"`
	Date                      string  `json:"date"`
	WarningLevel              string  `json:"warning_level"`
	CalibratedRiskProbability float64 `json:"calibrated_risk_probability"`
	TrustScore                float64 `json:"trust_score"`
}

func buildTickerList(batch warnings.PredictionBatch) TickerListResponse {
	tickers := make([]TickerSummary, 0, len(batch.Records))
	for _, record := range batch.Records {
		tickers = append(tickers, TickerSummary{
			Ticker:                    record.Ticker,
			Market:                    inferTickerMarket(record.Ticker),
			Date:                      record.Date,
			WarningLevel:              record.WarningLevel,
			CalibratedRiskProbability: record.CalibratedRiskProbability,
			TrustScore:                record.TrustScore,
		})
	}
	sort.SliceStable(tickers, func(left int, right int) bool {
		return tickers[left].Ticker < tickers[right].Ticker
	})
	return TickerListResponse{
		SchemaVersion: tickerListSchemaVersion,
		RunID:         batch.RunID,
		DataAsOf:      batch.DataAsOf,
		GeneratedAt:   batch.GeneratedAt,
		RecordCount:   len(tickers),
		Tickers:       tickers,
	}
}

func inferTickerMarket(ticker string) string {
	value := strings.TrimSpace(strings.ToUpper(ticker))
	if value == "" {
		return "unknown"
	}
	if isDigits(value) || strings.HasSuffix(value, ".TW") || strings.HasSuffix(value, ".TWO") {
		return "taiwan"
	}
	return "us"
}

func isDigits(value string) bool {
	for _, char := range value {
		if char < '0' || char > '9' {
			return false
		}
	}
	return true
}
