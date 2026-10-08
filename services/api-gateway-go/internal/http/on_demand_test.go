package apihttp

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestCommandOnDemandAnalyzerPassesTickerAndDatabaseURL(t *testing.T) {
	tempDir := t.TempDir()
	outputPath := filepath.Join(tempDir, "capture.txt")
	scriptPath := filepath.Join(tempDir, "capture.sh")
	script := `#!/bin/sh
output="$1"
printf '%s\n' "$TSI_DATABASE_URL" > "$output"
shift
printf '%s\n' "$@" >> "$output"
`
	if err := os.WriteFile(scriptPath, []byte(script), 0o755); err != nil {
		t.Fatalf("write script: %v", err)
	}
	analyzer, err := NewCommandOnDemandAnalyzer(
		"sh "+scriptPath+" "+outputPath,
		"postgresql://user:password@localhost:5432/db",
		"",
		5*time.Second,
	)
	if err != nil {
		t.Fatalf("NewCommandOnDemandAnalyzer returned error: %v", err)
	}

	if err := analyzer.Analyze(context.Background(), "2884"); err != nil {
		t.Fatalf("Analyze returned error: %v", err)
	}

	data, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatalf("read output: %v", err)
	}
	text := string(data)
	if !strings.Contains(text, "postgresql://user:password@localhost:5432/db") {
		t.Fatalf("database URL was not passed through env: %q", text)
	}
	if !strings.Contains(text, "--ticker\n2884") {
		t.Fatalf("ticker args missing from command output: %q", text)
	}
}

type gatedAnalyzer struct {
	mu       sync.Mutex
	calls    map[string]int
	contexts []context.Context
	started  chan string
	release  chan struct{}
}

func newGatedAnalyzer() *gatedAnalyzer {
	return &gatedAnalyzer{
		calls:   map[string]int{},
		started: make(chan string, 8),
		release: make(chan struct{}),
	}
}

func (g *gatedAnalyzer) Analyze(ctx context.Context, ticker string) error {
	g.mu.Lock()
	g.calls[ticker]++
	g.contexts = append(g.contexts, ctx)
	g.mu.Unlock()
	g.started <- ticker
	<-g.release
	return nil
}

func TestLimitedOnDemandAnalyzerSharesOneRunPerTicker(t *testing.T) {
	gated := newGatedAnalyzer()
	limited, err := NewLimitedOnDemandAnalyzer(gated, 2)
	if err != nil {
		t.Fatalf("NewLimitedOnDemandAnalyzer: %v", err)
	}
	results := make(chan error, 4)
	go func() { results <- limited.Analyze(context.Background(), "2330") }()
	<-gated.started
	for _, ticker := range []string{"2330", " 2330 ", "2330"} {
		go func() { results <- limited.Analyze(context.Background(), ticker) }()
	}
	time.Sleep(50 * time.Millisecond)
	close(gated.release)

	for range 4 {
		if err := <-results; err != nil {
			t.Fatalf("Analyze returned error: %v", err)
		}
	}
	if gated.calls["2330"] != 1 {
		t.Fatalf("calls = %v, want one shared run", gated.calls)
	}
}

func TestLimitedOnDemandAnalyzerRejectsWhenSlotsAreFull(t *testing.T) {
	gated := newGatedAnalyzer()
	limited, err := NewLimitedOnDemandAnalyzer(gated, 1)
	if err != nil {
		t.Fatalf("NewLimitedOnDemandAnalyzer: %v", err)
	}
	first := make(chan error, 1)
	go func() { first <- limited.Analyze(context.Background(), "NVDA") }()
	<-gated.started

	if err := limited.Analyze(context.Background(), "2330"); !errors.Is(err, ErrOnDemandBusy) {
		t.Fatalf("second ticker error = %v, want ErrOnDemandBusy", err)
	}
	close(gated.release)
	if err := <-first; err != nil {
		t.Fatalf("first ticker error = %v", err)
	}
	if err := limited.Analyze(context.Background(), "2330"); err != nil {
		t.Fatalf("slot was not released: %v", err)
	}
}

func TestLimitedOnDemandAnalyzerKeepsSharedRunWhenCallerLeaves(t *testing.T) {
	gated := newGatedAnalyzer()
	limited, err := NewLimitedOnDemandAnalyzer(gated, 1)
	if err != nil {
		t.Fatalf("NewLimitedOnDemandAnalyzer: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() { result <- limited.Analyze(ctx, "2330") }()
	<-gated.started
	cancel()

	if err := <-result; !errors.Is(err, context.Canceled) {
		t.Fatalf("caller error = %v, want context.Canceled", err)
	}
	gated.mu.Lock()
	runCtx := gated.contexts[0]
	gated.mu.Unlock()
	if runCtx.Err() != nil {
		t.Fatalf("shared run context was canceled with its first caller: %v", runCtx.Err())
	}
	close(gated.release)
}

func TestNewLimitedOnDemandAnalyzerValidatesArguments(t *testing.T) {
	if _, err := NewLimitedOnDemandAnalyzer(nil, 1); err == nil {
		t.Fatal("nil analyzer was accepted")
	}
	if _, err := NewLimitedOnDemandAnalyzer(newGatedAnalyzer(), 0); err == nil {
		t.Fatal("zero concurrency was accepted")
	}
}
