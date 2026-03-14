CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    event_type VARCHAR(120) NOT NULL,
    aggregate_type VARCHAR(60) NOT NULL,
    aggregate_id UUID NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_status_available
ON outbox_events(status, available_at, created_at);

CREATE TABLE IF NOT EXISTS notary_entries (
    id UUID PRIMARY KEY,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL CHECK (turn_number >= 0),
    based_on_message_count INTEGER NOT NULL CHECK (based_on_message_count >= 0),
    window_size INTEGER NOT NULL CHECK (window_size > 0),
    summary_text TEXT NOT NULL,
    facts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mission_progress_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    open_threads_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_notary_entries_game_turn_message_count UNIQUE (game_id, turn_number, based_on_message_count)
);

CREATE INDEX IF NOT EXISTS idx_notary_entries_game_turn
ON notary_entries(game_id, turn_number DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS scene_snapshots (
    game_id UUID PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
    source_notary_entry_id UUID NOT NULL REFERENCES notary_entries(id) ON DELETE RESTRICT,
    version_turn INTEGER NOT NULL CHECK (version_turn >= 0),
    facts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mission_progress_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    open_threads_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary_text TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
