-- Email messages table for storing processed emails
CREATE TABLE IF NOT EXISTS email_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_id TEXT UNIQUE NOT NULL,
    thread_id TEXT NOT NULL,
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    response TEXT,
    received_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for checking if email was processed
CREATE INDEX IF NOT EXISTS idx_email_messages_gmail_id ON email_messages(gmail_id);

-- Index for fetching thread history
CREATE INDEX IF NOT EXISTS idx_email_messages_thread_id ON email_messages(thread_id);
