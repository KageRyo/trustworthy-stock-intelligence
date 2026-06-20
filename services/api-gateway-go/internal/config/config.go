package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultAddress = ":8080"
)

type Config struct {
	Address                         string
	DatabaseURL                     string
	CORSAllowedOrigins              []string
	OnDemandAnalysisCommand         string
	OnDemandAnalysisWorkdir         string
	OnDemandAnalysisTimeoutDuration time.Duration
}

func Load() Config {
	address := envOrDefault("TSI_API_ADDR", defaultAddress)
	if port := os.Getenv("PORT"); port != "" && os.Getenv("TSI_API_ADDR") == "" {
		if _, err := strconv.Atoi(port); err == nil {
			address = ":" + port
		}
	}
	return Config{
		Address:                         address,
		DatabaseURL:                     envOrDefault("TSI_DATABASE_URL", ""),
		CORSAllowedOrigins:              splitCSV(envOrDefault("TSI_CORS_ALLOWED_ORIGINS", "*")),
		OnDemandAnalysisCommand:         envOrDefault("TSI_ON_DEMAND_ANALYSIS_COMMAND", ""),
		OnDemandAnalysisWorkdir:         envOrDefault("TSI_ON_DEMAND_ANALYSIS_WORKDIR", ""),
		OnDemandAnalysisTimeoutDuration: secondsEnv("TSI_ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS", 120),
	}
}

func envOrDefault(name string, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}

func splitCSV(value string) []string {
	parts := strings.Split(value, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			values = append(values, trimmed)
		}
	}
	return values
}

func secondsEnv(name string, fallback int) time.Duration {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return time.Duration(fallback) * time.Second
	}
	seconds, err := strconv.Atoi(value)
	if err != nil || seconds < 1 {
		return time.Duration(fallback) * time.Second
	}
	return time.Duration(seconds) * time.Second
}
