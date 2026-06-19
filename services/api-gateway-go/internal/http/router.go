package apihttp

import "net/http"

func NewRouter(handlers *Handlers) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /metrics", handlers.Metrics)
	mux.HandleFunc("GET /openapi.yaml", handlers.OpenAPI)
	mux.HandleFunc("GET /swagger", handlers.Swagger)
	mux.HandleFunc("GET /swagger/", handlers.Swagger)
	mux.HandleFunc("GET /api/v1/status", handlers.Status)
	mux.HandleFunc("GET /api/v1/tickers", handlers.Tickers)
	mux.HandleFunc("GET /api/v1/analysis/{ticker}", handlers.TickerAnalysis)
	mux.HandleFunc("GET /api/v1/warnings/latest", handlers.LatestWarnings)
	mux.HandleFunc("GET /api/v1/warnings/{ticker}", handlers.TickerWarning)
	mux.HandleFunc("GET /api/v1/models/current", handlers.CurrentModel)
	return mux
}
