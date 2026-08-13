package observability

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Labels are intentionally small, stable, and non-secret. Callers should use
// route templates rather than raw ticker/job identifiers.
type Labels map[string]string

type metricKey struct {
	name   string
	labels string
}

// Registry is a lightweight in-process Prometheus-compatible registry. It is
// deliberately dependency-free and safe to update from concurrent requests.
type Registry struct {
	mu       sync.RWMutex
	counters map[metricKey]uint64
	gauges   map[metricKey]float64
	durations map[metricKey]durationValue
}

type durationValue struct {
	seconds float64
	count   uint64
}

func NewRegistry() *Registry {
	return &Registry{
		counters:  map[metricKey]uint64{},
		gauges:    map[metricKey]float64{},
		durations: map[metricKey]durationValue{},
	}
}

func (r *Registry) IncCounter(name string, labels Labels) {
	if r == nil {
		return
	}
	key := metricKey{name: name, labels: formatLabels(labels)}
	r.mu.Lock()
	r.counters[key]++
	r.mu.Unlock()
}

func (r *Registry) SetGauge(name string, labels Labels, value float64) {
	if r == nil {
		return
	}
	key := metricKey{name: name, labels: formatLabels(labels)}
	r.mu.Lock()
	r.gauges[key] = value
	r.mu.Unlock()
}

func (r *Registry) ObserveDuration(name string, labels Labels, duration time.Duration) {
	if r == nil {
		return
	}
	key := metricKey{name: name, labels: formatLabels(labels)}
	r.mu.Lock()
	value := r.durations[key]
	value.seconds += duration.Seconds()
	value.count++
	r.durations[key] = value
	r.mu.Unlock()
}

func (r *Registry) Render() string {
	if r == nil {
		return ""
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	lines := []string{
		"# TYPE tsi_api_requests_total counter",
	}
	keys := make([]metricKey, 0, len(r.counters))
	for key := range r.counters {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool { return metricKeyString(keys[i]) < metricKeyString(keys[j]) })
	for _, key := range keys {
		lines = append(lines, metricKeyString(key)+" "+strconv.FormatUint(r.counters[key], 10))
	}
	lines = append(lines, "# TYPE tsi_api_request_duration_seconds summary")
	durationKeys := make([]metricKey, 0, len(r.durations))
	for key := range r.durations {
		durationKeys = append(durationKeys, key)
	}
	sort.Slice(durationKeys, func(i, j int) bool { return metricKeyString(durationKeys[i]) < metricKeyString(durationKeys[j]) })
	for _, key := range durationKeys {
		value := r.durations[key]
		lines = append(lines,
			metricKeyString(metricKey{name: key.name + "_seconds_sum", labels: key.labels})+" "+strconv.FormatFloat(value.seconds, 'f', 6, 64),
			metricKeyString(metricKey{name: key.name + "_count", labels: key.labels})+" "+strconv.FormatUint(value.count, 10),
		)
	}
	lines = append(lines, "# TYPE tsi_api_gauge gauge")
	gaugeKeys := make([]metricKey, 0, len(r.gauges))
	for key := range r.gauges {
		gaugeKeys = append(gaugeKeys, key)
	}
	sort.Slice(gaugeKeys, func(i, j int) bool { return metricKeyString(gaugeKeys[i]) < metricKeyString(gaugeKeys[j]) })
	for _, key := range gaugeKeys {
		lines = append(lines, metricKeyString(key)+" "+strconv.FormatFloat(r.gauges[key], 'f', 6, 64))
	}
	return strings.Join(lines, "\n") + "\n"
}

func formatLabels(labels Labels) string {
	if len(labels) == 0 {
		return ""
	}
	keys := make([]string, 0, len(labels))
	for key := range labels {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf(`%s=%q`, key, labels[key]))
	}
	return "{" + strings.Join(parts, ",") + "}"
}

func metricKeyString(key metricKey) string {
	return key.name + key.labels
}

// RouteTemplate prevents raw tickers, watchlist names, and job IDs from
// creating unbounded metric cardinality.
func RouteTemplate(path string) string {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) >= 4 && parts[0] == "api" && parts[1] == "v1" {
		switch parts[2] {
		case "analysis":
			parts[3] = ":ticker"
		case "warnings":
			parts[3] = ":ticker"
		case "watchlists":
			parts[3] = ":name"
		case "prediction-jobs":
			parts[3] = ":id"
		}
	}
	if len(parts) == 0 || parts[0] == "" {
		return "/"
	}
	return "/" + strings.Join(parts, "/")
}
