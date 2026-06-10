package config

import (
	"os"
	"strconv"
)

const (
	defaultAddress      = ":8080"
	defaultWarningsPath = "data/artifacts/latest_warnings.json"
)

type Config struct {
	Address      string
	WarningsPath string
}

func Load() Config {
	address := envOrDefault("TSI_API_ADDR", defaultAddress)
	if port := os.Getenv("PORT"); port != "" && os.Getenv("TSI_API_ADDR") == "" {
		if _, err := strconv.Atoi(port); err == nil {
			address = ":" + port
		}
	}
	return Config{
		Address:      address,
		WarningsPath: envOrDefault("TSI_WARNINGS_PATH", defaultWarningsPath),
	}
}

func envOrDefault(name string, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}
