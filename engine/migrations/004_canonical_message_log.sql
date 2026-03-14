ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS author VARCHAR(255);

UPDATE messages
SET author = COALESCE(NULLIF(metadata_json->>'author', ''), role)
WHERE author IS NULL OR author = '';

ALTER TABLE messages
    ALTER COLUMN author SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_messages_game_created_at ON messages(game_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_game_turn_created_at ON messages(game_id, turn_number, created_at);

UPDATE game_states
SET state_json = state_json - 'messages'
WHERE state_json ? 'messages';
