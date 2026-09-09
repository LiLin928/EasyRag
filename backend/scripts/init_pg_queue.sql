-- Init execution_events table

CREATE TABLE IF NOT EXISTS execution_events (
    id BIGSERIAL PRIMARY KEY,
    execution_id TEXT NOT NULL,
    event VARCHAR(100) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_events_eid_seq ON execution_events(execution_id, seq);

