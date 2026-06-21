package apihttp

import (
	"regexp"
	"sort"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

const tickerListSchemaVersion = "ticker_list.v1"

var taiwanLocalTickerPattern = regexp.MustCompile(`^[0-9]{4,6}[A-Z]?$`)

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
	if isTaiwanLocalTicker(value) ||
		strings.HasSuffix(value, ".TW") ||
		strings.HasSuffix(value, ".TWO") ||
		strings.HasSuffix(value, ".EMERGING") {
		return "taiwan"
	}
	return "us"
}

func isTaiwanLocalTicker(value string) bool {
	normalized := strings.TrimSuffix(
		strings.TrimSuffix(
			strings.TrimSuffix(strings.ToUpper(strings.TrimSpace(value)), ".TW"),
			".TWO",
		),
		".EMERGING",
	)
	return taiwanLocalTickerPattern.MatchString(normalized)
}
