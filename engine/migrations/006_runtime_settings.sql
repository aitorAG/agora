CREATE TABLE IF NOT EXISTS runtime_settings (
    key VARCHAR(120) PRIMARY KEY,
    value_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runtime_settings_updated_at
ON runtime_settings(updated_at DESC);
