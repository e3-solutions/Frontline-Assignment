-- Migration: Create email_tenant table for multi-tenant Outlook/email configuration
-- Each organization can have one email tenant configuration for automated email bot

CREATE TABLE IF NOT EXISTS email_tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Azure/Microsoft tenant configuration
    azure_tenant_id TEXT NOT NULL,
    mailbox TEXT NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add trigger for updated_at
CREATE TRIGGER update_email_tenant_updated_at
    BEFORE UPDATE ON email_tenant
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add nullable email_tenant_id to users table
-- Nullable because not all users/orgs will use the email bot feature
ALTER TABLE users
ADD COLUMN email_tenant_id UUID REFERENCES email_tenant(id) ON DELETE SET NULL;

-- Index for lookups
CREATE INDEX idx_users_email_tenant_id ON users(email_tenant_id) WHERE email_tenant_id IS NOT NULL;

COMMENT ON TABLE email_tenant IS 'Email tenant configuration for multi-tenant Outlook/email bot integration';
COMMENT ON COLUMN email_tenant.azure_tenant_id IS 'Azure AD tenant ID from admin consent flow';
COMMENT ON COLUMN email_tenant.mailbox IS 'Email address of the mailbox to monitor';
COMMENT ON COLUMN users.email_tenant_id IS 'Optional link to email tenant config for automated email handling';
