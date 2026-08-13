package apihttp

import "net/http"

func NewRouter(handlers *Handlers, corsConfigs ...CORSConfig) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /readyz", handlers.Readiness)
	mux.HandleFunc("GET /metrics", handlers.Metrics)
	mux.HandleFunc("GET /openapi.yaml", handlers.OpenAPI)
	mux.HandleFunc("GET /swagger", handlers.Swagger)
	mux.HandleFunc("GET /swagger/", handlers.Swagger)
	mux.HandleFunc("GET /api/v1/status", handlers.Status)
	mux.HandleFunc("GET /api/v1/providers/health", handlers.ProviderHealth)
	mux.HandleFunc("POST /api/v1/prediction-jobs", handlers.CreatePredictionJob)
	mux.HandleFunc("GET /api/v1/prediction-jobs/{id}", handlers.GetPredictionJob)
	mux.HandleFunc("GET /api/v1/tickers", handlers.Tickers)
	mux.HandleFunc("GET /api/v1/watchlists/{name}", handlers.Watchlist)
	mux.HandleFunc("POST /api/v1/watchlists/{name}/tickers", handlers.AddWatchlistTicker)
	mux.HandleFunc("DELETE /api/v1/watchlists/{name}/tickers/{ticker}", handlers.RemoveWatchlistTicker)
	mux.HandleFunc("GET /api/v1/analysis/{ticker}/history", handlers.TickerWarningHistory)
	mux.HandleFunc("GET /api/v1/analysis/{ticker}/transitions", handlers.TickerWarningTransitions)
	mux.HandleFunc("GET /api/v1/analysis/{ticker}", handlers.TickerAnalysis)
	mux.HandleFunc("GET /api/v1/warnings/latest", handlers.LatestWarnings)
	mux.HandleFunc("GET /api/v1/warnings/{ticker}", handlers.TickerWarning)
	mux.HandleFunc("GET /api/v1/models/current", handlers.CurrentModel)
	corsConfig := CORSConfig{AllowedOrigins: []string{"*"}}
	if len(corsConfigs) > 0 {
		corsConfig = corsConfigs[0]
	}
	return withCORS(withObservability(mux, handlers.MetricsRegistry(), handlers.logger), corsConfig)
}
