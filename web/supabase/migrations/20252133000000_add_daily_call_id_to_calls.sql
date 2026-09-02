ALTER TABLE calls ADD COLUMN daily_call_id TEXT;

CREATE INDEX idx_calls_daily_call_id ON calls(daily_call_id);
