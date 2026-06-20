package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/config"
	apihttp "github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/http"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

func main() {
	cfg := config.Load()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	store, err := warnings.NewPostgresStore(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("load postgres warnings store: %v", err)
	}
	defer store.Close()
	watchlistStore, err := watchlist.NewPostgresStore(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("load postgres watchlist store: %v", err)
	}
	defer watchlistStore.Close()
	router := apihttp.NewRouter(
		apihttp.NewHandlers(store, watchlistStore),
		apihttp.CORSConfig{AllowedOrigins: cfg.CORSAllowedOrigins},
	)
	log.Printf("starting TSI API gateway on %s using PostgreSQL", cfg.Address)
	if err := http.ListenAndServe(cfg.Address, router); err != nil {
		log.Fatalf("server stopped: %v", err)
	}
}
