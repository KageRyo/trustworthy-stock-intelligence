package warnings

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

type FileStore struct {
	mu             sync.RWMutex
	path           string
	batch          PredictionBatch
	byKey          map[string]PredictionRecord
	fileModifiedAt time.Time
	lastLoadedAt   time.Time
	lastError      string
}

type StoreStatus struct {
	WarningsPath   string `json:"warnings_path"`
	WarningsLoaded bool   `json:"warnings_loaded"`
	SchemaVersion  string `json:"schema_version"`
	RunID          string `json:"run_id"`
	DataAsOf       string `json:"data_as_of"`
	GeneratedAt    string `json:"generated_at"`
	RecordCount    int    `json:"record_count"`
	LastLoadedAt   string `json:"last_loaded_at"`
	FileModifiedAt string `json:"file_modified_at"`
	LastError      string `json:"last_error,omitempty"`
}

func NewFileStore(path string) (*FileStore, error) {
	store := &FileStore{path: path}
	if err := store.reload(); err != nil {
		return nil, err
	}
	return store, nil
}

func (s *FileStore) Batch() PredictionBatch {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.batch
}

func (s *FileStore) FindTicker(ticker string) (PredictionRecord, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	record, ok := s.byKey[strings.ToUpper(ticker)]
	return record, ok
}

func (s *FileStore) History(ticker string, limit int) ([]WarningHistoryRecord, error) {
	if limit < 1 {
		return []WarningHistoryRecord{}, nil
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	record, ok := s.byKey[strings.ToUpper(ticker)]
	if !ok {
		return []WarningHistoryRecord{}, nil
	}
	return []WarningHistoryRecord{HistoryRecordFromPrediction(record)}, nil
}

func (s *FileStore) Refresh() error {
	info, err := os.Stat(s.path)
	if err != nil {
		s.setLastError(fmt.Errorf("stat warnings file %q: %w", s.path, err))
		return fmt.Errorf("stat warnings file %q: %w", s.path, err)
	}

	s.mu.RLock()
	unchanged := !s.fileModifiedAt.IsZero() && info.ModTime().Equal(s.fileModifiedAt)
	s.mu.RUnlock()
	if unchanged {
		return nil
	}

	if err := s.reload(); err != nil {
		s.setLastError(err)
		return err
	}
	return nil
}

func (s *FileStore) Status() StoreStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return StoreStatus{
		WarningsPath:   s.path,
		WarningsLoaded: len(s.batch.Records) > 0,
		SchemaVersion:  s.batch.SchemaVersion,
		RunID:          s.batch.RunID,
		DataAsOf:       s.batch.DataAsOf,
		GeneratedAt:    s.batch.GeneratedAt,
		RecordCount:    s.batch.RecordCount,
		LastLoadedAt:   formatTime(s.lastLoadedAt),
		FileModifiedAt: formatTime(s.fileModifiedAt),
		LastError:      s.lastError,
	}
}

func (s *FileStore) reload() error {
	batch, byKey, modifiedAt, err := loadFile(s.path)
	if err != nil {
		return err
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	s.batch = batch
	s.byKey = byKey
	s.fileModifiedAt = modifiedAt
	s.lastLoadedAt = time.Now().UTC()
	s.lastError = ""
	return nil
}

func (s *FileStore) setLastError(err error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastError = err.Error()
}

func loadFile(path string) (PredictionBatch, map[string]PredictionRecord, time.Time, error) {
	info, err := os.Stat(path)
	if err != nil {
		return PredictionBatch{}, nil, time.Time{}, fmt.Errorf("stat warnings file %q: %w", path, err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return PredictionBatch{}, nil, time.Time{}, fmt.Errorf("read warnings file %q: %w", path, err)
	}

	var batch PredictionBatch
	if err := json.Unmarshal(data, &batch); err != nil {
		return PredictionBatch{}, nil, time.Time{}, fmt.Errorf("decode warnings file %q: %w", path, err)
	}
	if batch.RecordCount == 0 {
		batch.RecordCount = len(batch.Records)
	}
	if batch.SchemaVersion == "" {
		batch.SchemaVersion = "v1"
	}
	if batch.RunID == "" {
		batch.RunID = "unknown"
	}
	if batch.RecordCount != len(batch.Records) {
		return PredictionBatch{}, nil, time.Time{}, fmt.Errorf(
			"warnings file %q has record_count=%d but %d records",
			path,
			batch.RecordCount,
			len(batch.Records),
		)
	}
	byKey := make(map[string]PredictionRecord, len(batch.Records))
	for index, record := range batch.Records {
		record.RunID = batch.RunID
		record.DataAsOf = batch.DataAsOf
		record.GeneratedAt = batch.GeneratedAt
		batch.Records[index] = record
		byKey[strings.ToUpper(record.Ticker)] = record
	}
	return batch, byKey, info.ModTime(), nil
}

func formatTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}
