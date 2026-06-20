package apihttp

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
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
