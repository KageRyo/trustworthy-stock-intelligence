-- Primary warning-change events derived from adjacent warning snapshots.
CREATE TABLE IF NOT EXISTS warning_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker_id UUID NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    previous_batch_id UUID REFERENCES prediction_batches(id) ON DELETE SET NULL,
    current_batch_id UUID NOT NULL REFERENCES prediction_batches(id) ON DELETE CASCADE,
    previous_warning_level TEXT CHECK (previous_warning_level IN ('alert', 'watch', 'abstain', 'no_alert')),
    current_warning_level TEXT NOT NULL CHECK (current_warning_level IN ('alert', 'watch', 'abstain', 'no_alert')),
    transition_type TEXT NOT NULL CHECK (
        transition_type IN (
            'new_watch', 'new_alert', 'upgraded', 'downgraded', 'resolved',
            'persistent_alert', 'low_trust_warning'
        )
    ),
    previous_run_id TEXT,
    current_run_id TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    deduplication_key TEXT NOT NULL UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS warning_transitions_ticker_detected_idx
    ON warning_transitions (ticker_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS warning_transitions_type_idx
    ON warning_transitions (transition_type, detected_at DESC);
