CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS game_configs (
    game_id UUID PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
    config_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS game_states (
    game_id UUID PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL CHECK (turn_number >= 0),
    role VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_game_id ON messages(game_id);
CREATE INDEX IF NOT EXISTS idx_messages_game_turn ON messages(game_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id);
