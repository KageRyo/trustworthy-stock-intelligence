// Package freshness contains the serving-side freshness safety policy.
package freshness

import (
	"strings"
	"time"
)

const SchemaVersion = "freshness.v1"

type State string

const (
	StateFresh    State = "fresh"
	StateStale    State = "stale"
	StateUnusable State = "unusable"
)

type Action string

const (
	ActionAllow     Action = "allow"
	ActionDowngrade Action = "downgrade"
	ActionBlock     Action = "block"
)

type Assessment struct {
	SchemaVersion        string   `json:"schema_version"`
	Market               string   `json:"market"`
	Interval             string   `json:"interval"`
	DataAsOf             string   `json:"data_as_of"`
	EvaluatedAt          string   `json:"evaluated_at"`
	AgeSeconds           *float64 `json:"age_seconds,omitempty"`
	FreshWithinSeconds   int      `json:"fresh_within_seconds"`
	StaleWithinSeconds   int      `json:"stale_within_seconds"`
	State                State    `json:"state"`
	Action               Action   `json:"action"`
	ReasonCode           string   `json:"reason_code"`
	WarningLevelOverride string   `json:"warning_level_override,omitempty"`
	Message              string   `json:"message"`
}

type threshold struct {
	fresh int
	stale int
}

var thresholds = map[string]threshold{
	"us:1m":       {fresh: 120, stale: 900},
	"us:5m":       {fresh: 600, stale: 3600},
	"us:1d":       {fresh: 36 * 3600, stale: 5 * 86400},
	"twse:1m":     {fresh: 120, stale: 900},
	"twse:5m":     {fresh: 600, stale: 3600},
	"twse:1d":     {fresh: 36 * 3600, stale: 5 * 86400},
	"tpex:1m":     {fresh: 120, stale: 900},
	"tpex:5m":     {fresh: 600, stale: 3600},
	"tpex:1d":     {fresh: 36 * 3600, stale: 5 * 86400},
	"emerging:1m": {fresh: 120, stale: 900},
	"emerging:5m": {fresh: 600, stale: 3600},
	"emerging:1d": {fresh: 36 * 3600, stale: 5 * 86400},
	"taiwan:1m":   {fresh: 120, stale: 900},
	"taiwan:5m":   {fresh: 600, stale: 3600},
	"taiwan:1d":   {fresh: 36 * 3600, stale: 5 * 86400},
	"unknown:1m":  {fresh: 120, stale: 900},
	"unknown:5m":  {fresh: 600, stale: 3600},
	"unknown:1d":  {fresh: 36 * 3600, stale: 5 * 86400},
}

func thresholdFor(market, interval string) threshold {
	interval = strings.ToLower(strings.TrimSpace(interval))
	if interval != "1m" && interval != "5m" && interval != "1d" {
		interval = "1d"
	}
	market = strings.ToLower(strings.TrimSpace(market))
	if market == "" {
		market = "unknown"
	}
	if value, ok := thresholds[market+":"+interval]; ok {
		return value
	}
	return thresholds["unknown:1d"]
}

func parseDataAsOf(value string) (time.Time, bool) {
	value = strings.TrimSpace(value)
	if value == "" {
		return time.Time{}, false
	}
	if parsed, err := time.Parse(time.RFC3339, value); err == nil {
		return parsed.UTC(), true
	}
	if parsed, err := time.Parse("2006-01-02", value); err == nil {
		return time.Date(parsed.Year(), parsed.Month(), parsed.Day(), 23, 59, 59, 0, time.UTC), true
	}
	return time.Time{}, false
}

func Assess(dataAsOf, evaluatedAt, market, interval string) Assessment {
	evaluated := time.Now().UTC()
	if parsed, err := time.Parse(time.RFC3339, strings.TrimSpace(evaluatedAt)); err == nil {
		evaluated = parsed.UTC()
	}
	market = strings.ToLower(strings.TrimSpace(market))
	if market == "" {
		market = "unknown"
	}
	interval = strings.ToLower(strings.TrimSpace(interval))
	if interval != "1m" && interval != "5m" && interval != "1d" {
		interval = "1d"
	}
	limits := thresholdFor(market, interval)
	assessment := Assessment{
		SchemaVersion:      SchemaVersion,
		Market:             market,
		Interval:           interval,
		DataAsOf:           dataAsOf,
		EvaluatedAt:        evaluated.Format(time.RFC3339),
		FreshWithinSeconds: limits.fresh,
		StaleWithinSeconds: limits.stale,
	}
	parsed, ok := parseDataAsOf(dataAsOf)
	if !ok {
		assessment.State = StateUnusable
		assessment.Action = ActionBlock
		assessment.ReasonCode = "freshness_missing_data_as_of"
		assessment.WarningLevelOverride = "abstain"
		assessment.Message = "The prediction has no data cutoff and must not be served as actionable."
		return assessment
	}
	age := evaluated.Sub(parsed).Seconds()
	if age < 0 {
		age = 0
		assessment.State = StateUnusable
		assessment.Action = ActionBlock
		assessment.ReasonCode = "freshness_future_data_as_of"
		assessment.WarningLevelOverride = "abstain"
		assessment.Message = "The prediction cutoff is in the future and must not be served."
	} else if age <= float64(limits.fresh) {
		assessment.State = StateFresh
		assessment.Action = ActionAllow
		assessment.ReasonCode = "freshness_fresh"
		assessment.Message = "The prediction cutoff is within the configured freshness window."
	} else if age <= float64(limits.stale) {
		assessment.State = StateStale
		assessment.Action = ActionDowngrade
		assessment.ReasonCode = "freshness_stale"
		assessment.WarningLevelOverride = "abstain"
		assessment.Message = "The prediction is retained for context but is too old for a full-confidence warning."
	} else {
		assessment.State = StateUnusable
		assessment.Action = ActionBlock
		assessment.ReasonCode = "freshness_unusable"
		assessment.WarningLevelOverride = "abstain"
		assessment.Message = "The prediction is beyond the usable freshness window and must be treated as abstain."
	}
	assessment.AgeSeconds = &age
	return assessment
}
