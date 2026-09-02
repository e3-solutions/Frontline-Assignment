-- Create processed_emails table for deduplication/locking
-- This table tracks which emails have been claimed for processing to prevent duplicates

CREATE TABLE IF NOT EXISTS processed_emails (
    email_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cleanup queries (optional: delete old entries periodically)
CREATE INDEX idx_processed_emails_created_at ON processed_emails(created_at);

COMMENT ON TABLE processed_emails IS 'Tracks claimed emails to prevent duplicate processing from webhook retries';
