package config

import (
	"os"
	"strconv"
	"strings"
)

const (
	defaultAddress = ":8080"
)

type Config struct {
	Address            string
	DatabaseURL        string
	CORSAllowedOrigins []string
}

func Load() Config {
	address := envOrDefault("TSI_API_ADDR", defaultAddress)
	if port := os.Getenv("PORT"); port != "" && os.Getenv("TSI_API_ADDR") == "" {
		if _, err := strconv.Atoi(port); err == nil {
			address = ":" + port
		}
	}
	return Config{
		Address:            address,
		DatabaseURL:        envOrDefault("TSI_DATABASE_URL", ""),
		CORSAllowedOrigins: splitCSV(envOrDefault("TSI_CORS_ALLOWED_ORIGINS", "*")),
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
