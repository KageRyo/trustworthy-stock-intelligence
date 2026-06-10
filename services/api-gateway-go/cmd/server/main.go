package main

import (
	"log"
	"net/http"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/config"
	apihttp "github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/http"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

func main() {
	cfg := config.Load()
	store, err := warnings.NewFileStore(cfg.WarningsPath)
	if err != nil {
		log.Fatalf("load warnings store: %v", err)
	}
	router := apihttp.NewRouter(apihttp.NewHandlers(store))
	log.Printf("starting TSI API gateway on %s using warnings file %s", cfg.Address, cfg.WarningsPath)
	if err := http.ListenAndServe(cfg.Address, router); err != nil {
		log.Fatalf("server stopped: %v", err)
	}
}
