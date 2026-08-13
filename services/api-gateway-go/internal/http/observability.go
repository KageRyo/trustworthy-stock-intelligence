package apihttp

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/observability"
)

type statusRecorder struct {
	http.ResponseWriter
	status  int
	written bool
}

func (w *statusRecorder) WriteHeader(status int) {
	if w.written {
		return
	}
	w.status = status
	w.written = true
	w.ResponseWriter.WriteHeader(status)
}

func (w *statusRecorder) Write(body []byte) (int, error) {
	if !w.written {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(body)
}

func withObservability(next http.Handler, registry *observability.Registry, logger *slog.Logger) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		started := time.Now()
		recorder := &statusRecorder{ResponseWriter: response, status: http.StatusOK}
		next.ServeHTTP(recorder, request)
		if !recorder.written {
			recorder.status = http.StatusOK
		}
		route := observability.RouteTemplate(request.URL.Path)
		labels := observability.Labels{
			"method": request.Method,
			"path":   route,
			"status": http.StatusText(recorder.status),
		}
		registry.IncCounter("tsi_api_requests_total", labels)
		registry.ObserveDuration("tsi_api_request_duration", observability.Labels{
			"method": request.Method,
			"path":   route,
		}, time.Since(started))
		if logger != nil {
			logger.Info("http_request",
				"schema_version", "tsi_log.v1",
				"event", "http_request",
				"method", request.Method,
				"path", route,
				"status", recorder.status,
				"duration_ms", time.Since(started).Seconds()*1000,
			)
		}
	})
}
