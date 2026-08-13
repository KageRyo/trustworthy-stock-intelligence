package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/config"
	apihttp "github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/http"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/jobs"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	cfg := config.Load()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	store, err := warnings.NewPostgresStore(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("service_start_failed", "schema_version", "tsi_log.v1", "service", "api_gateway", "stage", "warnings_store", "error", err)
		os.Exit(1)
	}
	defer store.Close()
	watchlistStore, err := watchlist.NewPostgresStore(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("service_start_failed", "schema_version", "tsi_log.v1", "service", "api_gateway", "stage", "watchlist_store", "error", err)
		os.Exit(1)
	}
	defer watchlistStore.Close()
	predictionJobStore, err := jobs.NewPostgresStore(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("service_start_failed", "schema_version", "tsi_log.v1", "service", "api_gateway", "stage", "prediction_job_store", "error", err)
		os.Exit(1)
	}
	defer predictionJobStore.Close()
	handlers := apihttp.NewHandlers(store, watchlistStore)
	handlers.SetLogger(logger)
	handlers.SetProviderHealthStore(store)
	handlers.SetWarningTransitionStore(store)
	handlers.SetPredictionJobStore(predictionJobStore)
	if cfg.OnDemandAnalysisCommand != "" {
		analyzer, err := apihttp.NewCommandOnDemandAnalyzer(
			cfg.OnDemandAnalysisCommand,
			cfg.DatabaseURL,
			cfg.OnDemandAnalysisWorkdir,
			cfg.OnDemandAnalysisTimeoutDuration,
		)
		if err != nil {
			logger.Error("service_start_failed", "schema_version", "tsi_log.v1", "service", "api_gateway", "stage", "on_demand_analyzer", "error", err)
			os.Exit(1)
		}
		handlers.SetOnDemandAnalyzer(analyzer)
		logger.Info("on_demand_analysis_enabled", "schema_version", "tsi_log.v1", "service", "api_gateway")
	}
	router := apihttp.NewRouter(
		handlers,
		apihttp.CORSConfig{AllowedOrigins: cfg.CORSAllowedOrigins},
	)
	logger.Info("service_started", "schema_version", "tsi_log.v1", "service", "api_gateway", "address", cfg.Address, "dependency", "postgresql")
	if err := http.ListenAndServe(cfg.Address, router); err != nil {
		logger.Error("service_stopped", "schema_version", "tsi_log.v1", "service", "api_gateway", "error", err)
		os.Exit(1)
	}
}
