package apihttp

import (
	"net/http"
	"strings"
)

type CORSConfig struct {
	AllowedOrigins []string
}

func withCORS(next http.Handler, config CORSConfig) http.Handler {
	allowedOrigins := normalizeOrigins(config.AllowedOrigins)
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		origin := strings.TrimSpace(request.Header.Get("Origin"))
		allowedOrigin, allowed := matchAllowedOrigin(origin, allowedOrigins)
		if origin != "" && allowed {
			response.Header().Set("Access-Control-Allow-Origin", allowedOrigin)
			response.Header().Set("Vary", "Origin")
			response.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
			response.Header().Set("Access-Control-Allow-Headers", "Accept, Authorization, Content-Type")
			response.Header().Set("Access-Control-Max-Age", "600")
		}
		if request.Method == http.MethodOptions {
			if origin != "" && !allowed {
				response.WriteHeader(http.StatusForbidden)
				return
			}
			response.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(response, request)
	})
}

func normalizeOrigins(origins []string) []string {
	normalized := make([]string, 0, len(origins))
	for _, origin := range origins {
		value := strings.TrimSpace(origin)
		if value != "" {
			normalized = append(normalized, value)
		}
	}
	if len(normalized) == 0 {
		return []string{"*"}
	}
	return normalized
}

func matchAllowedOrigin(origin string, allowedOrigins []string) (string, bool) {
	if origin == "" {
		return "", false
	}
	for _, allowed := range allowedOrigins {
		if allowed == "*" {
			return "*", true
		}
		if strings.EqualFold(origin, allowed) {
			return origin, true
		}
	}
	return "", false
}
