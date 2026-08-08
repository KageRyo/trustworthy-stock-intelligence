ALTER TABLE warning_records
    ADD COLUMN IF NOT EXISTS feature_attributions JSONB NOT NULL DEFAULT '[]'::jsonb;
