package warnings

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

type FileStore struct {
	path  string
	batch PredictionBatch
	byKey map[string]PredictionRecord
}

func NewFileStore(path string) (*FileStore, error) {
	store := &FileStore{path: path}
	if err := store.load(); err != nil {
		return nil, err
	}
	return store, nil
}

func (s *FileStore) Batch() PredictionBatch {
	return s.batch
}

func (s *FileStore) FindTicker(ticker string) (PredictionRecord, bool) {
	record, ok := s.byKey[strings.ToUpper(ticker)]
	return record, ok
}

func (s *FileStore) load() error {
	data, err := os.ReadFile(s.path)
	if err != nil {
		return fmt.Errorf("read warnings file %q: %w", s.path, err)
	}
	var batch PredictionBatch
	if err := json.Unmarshal(data, &batch); err != nil {
		return fmt.Errorf("decode warnings file %q: %w", s.path, err)
	}
	if batch.RecordCount == 0 {
		batch.RecordCount = len(batch.Records)
	}
	if batch.RecordCount != len(batch.Records) {
		return fmt.Errorf("warnings file %q has record_count=%d but %d records", s.path, batch.RecordCount, len(batch.Records))
	}
	byKey := make(map[string]PredictionRecord, len(batch.Records))
	for _, record := range batch.Records {
		byKey[strings.ToUpper(record.Ticker)] = record
	}
	s.batch = batch
	s.byKey = byKey
	return nil
}
