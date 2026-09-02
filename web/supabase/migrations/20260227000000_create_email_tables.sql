-- Emails table (like phone_numbers but for email addresses)
CREATE TABLE IF NOT EXISTS emails (
    email TEXT PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    label TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_emails_org_id ON emails(org_id);

-- Email threads table
CREATE TABLE IF NOT EXISTS email_thread (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_email TEXT NOT NULL,
    client_email TEXT NOT NULL,
    thread_id TEXT UNIQUE NOT NULL,
    ended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email interactions table
CREATE TABLE IF NOT EXISTS email_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL REFERENCES email_thread(thread_id),
    bot_response TEXT,
    client_response TEXT,
    client_email_id TEXT,
    bot_email_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_thread_thread_id ON email_thread(thread_id);
CREATE INDEX IF NOT EXISTS idx_email_interactions_thread_id ON email_interactions(thread_id);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_email_thread_updated_at
    BEFORE UPDATE ON email_thread
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_email_interactions_updated_at
    BEFORE UPDATE ON email_interactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
