CREATE TABLE IF NOT EXISTS standard_templates (
    id VARCHAR(120) PRIMARY KEY,
    version VARCHAR(40) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_standard_templates_active
ON standard_templates(active, updated_at DESC);
