CREATE TABLE IF NOT EXISTS game_feedback (
    id UUID PRIMARY KEY,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    feedback_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_game_feedback_game_id ON game_feedback(game_id);
CREATE INDEX IF NOT EXISTS idx_game_feedback_user_id ON game_feedback(user_id);
