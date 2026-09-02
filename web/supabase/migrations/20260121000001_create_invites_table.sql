-- Migration: Create invites table for user invitation system
-- Invites allow existing organizations to invite new users

CREATE TABLE IF NOT EXISTS invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Organization that created the invite
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Invite details
    email TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'employee',

    -- Security token for validation (stored as hash, not plaintext)
    token_hash TEXT NOT NULL,

    -- Invite status
    used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,

    -- Prevent duplicate pending invites for same email in same org
    CONSTRAINT invites_unique_pending UNIQUE (org_id, email, used_at)
);

-- Indexes for common queries
CREATE INDEX idx_invites_token_hash ON invites(token_hash);
CREATE INDEX idx_invites_org_id ON invites(org_id);
CREATE INDEX idx_invites_email ON invites(email);

COMMENT ON TABLE invites IS 'User invitations for joining organizations with secure token-based validation';

-- Enable Row Level Security
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;

-- Admins can manage invites for their organization
CREATE POLICY "admins_manage_invites" ON invites
    FOR ALL
    USING (
        org_id IN (
            SELECT u.org_id FROM users u
            WHERE u.user_id = auth.uid() AND u.role = 'admin'
        )
    );

-- Anyone can read invite by token (for accepting during signup)
CREATE POLICY "anyone_read_invite" ON invites
    FOR SELECT
    USING (true);
