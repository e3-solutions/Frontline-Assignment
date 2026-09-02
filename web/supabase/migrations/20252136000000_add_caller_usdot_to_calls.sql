ALTER TABLE calls ADD COLUMN caller_usdot TEXT;

CREATE INDEX idx_calls_caller_usdot ON calls(caller_usdot);

