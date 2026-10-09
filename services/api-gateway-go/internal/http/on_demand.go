package apihttp

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"golang.org/x/sync/singleflight"
)

type OnDemandAnalyzer interface {
	Analyze(ctx context.Context, ticker string) error
}

type CommandOnDemandAnalyzer struct {
	command     []string
	databaseURL string
	workdir     string
	timeout     time.Duration
}

func NewCommandOnDemandAnalyzer(
	commandText string,
	databaseURL string,
	workdir string,
	timeout time.Duration,
) (*CommandOnDemandAnalyzer, error) {
	command := strings.Fields(strings.TrimSpace(commandText))
	if len(command) == 0 {
		return nil, errors.New("on-demand analysis command must not be empty")
	}
	if strings.TrimSpace(databaseURL) == "" {
		return nil, errors.New("TSI_DATABASE_URL is required for on-demand analysis")
	}
	if timeout <= 0 {
		return nil, errors.New("on-demand analysis timeout must be positive")
	}
	return &CommandOnDemandAnalyzer{
		command:     command,
		databaseURL: databaseURL,
		workdir:     strings.TrimSpace(workdir),
		timeout:     timeout,
	}, nil
}

func (a *CommandOnDemandAnalyzer) Analyze(ctx context.Context, ticker string) error {
	if strings.TrimSpace(ticker) == "" {
		return errors.New("ticker must not be empty")
	}
	runCtx, cancel := context.WithTimeout(ctx, a.timeout)
	defer cancel()

	args := append([]string{}, a.command[1:]...)
	args = append(args, "--ticker", strings.TrimSpace(ticker))
	cmd := exec.CommandContext(runCtx, a.command[0], args...)
	if a.workdir != "" {
		cmd.Dir = a.workdir
	}
	cmd.Env = append(os.Environ(), "TSI_DATABASE_URL="+a.databaseURL)
	output, err := cmd.CombinedOutput()
	if runCtx.Err() != nil {
		return fmt.Errorf("on-demand analysis timed out after %s for %s", a.timeout, ticker)
	}
	if err != nil {
		return fmt.Errorf(
			"on-demand analysis failed for %s: %w: %s",
			ticker,
			err,
			trimCommandOutput(output),
		)
	}
	return nil
}

func trimCommandOutput(output []byte) string {
	text := strings.TrimSpace(string(output))
	if len(text) <= 1000 {
		return text
	}
	return text[:1000] + "...[truncated]"
}

// ErrOnDemandBusy reports that every on-demand analysis slot is in use.
var ErrOnDemandBusy = errors.New("on-demand analysis capacity is full; retry shortly or queue a prediction job")

// LimitedOnDemandAnalyzer runs at most one analysis per ticker at a time and caps the number of
// tickers analyzed concurrently. Concurrent requests for the same ticker share one run. A full
// set of slots fails fast with ErrOnDemandBusy instead of queuing requests in memory.
type LimitedOnDemandAnalyzer struct {
	next  OnDemandAnalyzer
	slots chan struct{}
	group singleflight.Group
}

func NewLimitedOnDemandAnalyzer(next OnDemandAnalyzer, maxConcurrent int) (*LimitedOnDemandAnalyzer, error) {
	if next == nil {
		return nil, errors.New("on-demand analyzer must not be nil")
	}
	if maxConcurrent < 1 {
		return nil, errors.New("on-demand analysis concurrency must be at least 1")
	}
	return &LimitedOnDemandAnalyzer{next: next, slots: make(chan struct{}, maxConcurrent)}, nil
}

// Analyze joins an in-flight run for the same ticker or starts one if a slot is free. The shared
// run is detached from any single caller's cancellation, so one disconnecting client does not
// abort the analysis other callers are waiting for; the wrapped analyzer's own timeout still
// applies. Each caller stops waiting when its own context ends.
func (a *LimitedOnDemandAnalyzer) Analyze(ctx context.Context, ticker string) error {
	key := strings.ToUpper(strings.TrimSpace(ticker))
	results := a.group.DoChan(key, func() (any, error) {
		select {
		case a.slots <- struct{}{}:
		default:
			return nil, ErrOnDemandBusy
		}
		defer func() { <-a.slots }()
		return nil, a.next.Analyze(context.WithoutCancel(ctx), ticker)
	})
	select {
	case result := <-results:
		return result.Err
	case <-ctx.Done():
		return ctx.Err()
	}
}
