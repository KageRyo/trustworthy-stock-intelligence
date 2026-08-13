package observability

import (
	"strings"
	"testing"
	"time"
)

func TestRegistryRendersStableMetrics(t *testing.T) {
	registry := NewRegistry()
	registry.IncCounter("tsi_api_requests_total", Labels{"method": "GET", "path": "/api/v1/analysis/:ticker", "status": "200"})
	registry.ObserveDuration("tsi_api_request_duration", Labels{"method": "GET"}, 50*time.Millisecond)
	registry.SetGauge("tsi_api_queue_depth", Labels{"status": "queued"}, 2)

	output := registry.Render()
	for _, want := range []string{
		`tsi_api_requests_total{method="GET",path="/api/v1/analysis/:ticker",status="200"} 1`,
		`tsi_api_request_duration_seconds_count{method="GET"} 1`,
		`tsi_api_queue_depth{status="queued"} 2.000000`,
	} {
		if !strings.Contains(output, want) {
			t.Fatalf("metrics missing %q:\n%s", want, output)
		}
	}
}

func TestRouteTemplateBoundsIdentifiers(t *testing.T) {
	checks := map[string]string{
		"/api/v1/analysis/NVDA":                    "/api/v1/analysis/:ticker",
		"/api/v1/analysis/2330/transitions":       "/api/v1/analysis/:ticker/transitions",
		"/api/v1/watchlists/session-abc/tickers":   "/api/v1/watchlists/:name/tickers",
		"/api/v1/prediction-jobs/123":              "/api/v1/prediction-jobs/:id",
		"/health":                                  "/health",
	}
	for path, want := range checks {
		if got := RouteTemplate(path); got != want {
			t.Errorf("RouteTemplate(%q) = %q, want %q", path, got, want)
		}
	}
}
