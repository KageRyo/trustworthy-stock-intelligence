package apihttp

import (
	"context"
	"os"
	"path/filepath"
	"strings"
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
