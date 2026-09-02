-- Migration: Create phone_numbers table for multi-tenant phone assignment
-- Each phone number belongs to exactly one organization
-- This is the key for tenant differentiation at the bot level

CREATE TABLE IF NOT EXISTS phone_numbers (
    -- Phone number as primary key (each number is unique globally)
    phone_number TEXT PRIMARY KEY,

    -- Organization ownership
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Optional friendly label
    label TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- Index for organization lookups
CREATE INDEX idx_phone_numbers_org_id ON phone_numbers(org_id);

COMMENT ON TABLE phone_numbers IS 'Phone numbers assigned to organizations. Each number belongs to exactly one org for tenant isolation.';
COMMENT ON COLUMN phone_numbers.label IS 'Optional friendly name (e.g. "Main Line", "Support")';

-- Enable Row Level Security
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;

-- Users can see phone numbers in their organization (or superadmins see all)
CREATE POLICY "org_isolation_select" ON phone_numbers
    FOR SELECT USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Only admins can insert phone numbers for their organization
CREATE POLICY "admin_insert" ON phone_numbers
    FOR INSERT WITH CHECK (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid() AND role = 'admin')
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Only admins can update phone numbers in their organization
CREATE POLICY "admin_update" ON phone_numbers
    FOR UPDATE USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid() AND role = 'admin')
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Only admins can delete phone numbers from their organization
CREATE POLICY "admin_delete" ON phone_numbers
    FOR DELETE USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid() AND role = 'admin')
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );
