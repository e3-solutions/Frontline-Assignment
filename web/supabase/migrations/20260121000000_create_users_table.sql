-- Migration: Create users table for authentication and multi-tenancy
-- Users are linked to Supabase Auth and belong to one organization

-- Create enum type for user roles
CREATE TYPE user_role AS ENUM ('admin', 'employee');

CREATE TABLE IF NOT EXISTS users (
    -- user_id matches auth.users.id from Supabase Auth
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

    -- User details
    full_name TEXT NOT NULL,

    -- Organization relationship (multi-tenant)
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,

    -- User role within organization
    role user_role NOT NULL DEFAULT 'employee',

    -- Superadmin flag for cross-org access
    is_superadmin BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps (UTC, managed by database)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- Indexes for common queries
CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_superadmin ON users(is_superadmin) WHERE is_superadmin = true;

-- Trigger for updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE users IS 'Application users linked to Supabase Auth with multi-tenant organization support';
COMMENT ON COLUMN users.is_superadmin IS 'Superadmin users have elevated privileges across all organizations';

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile or if superadmin
CREATE POLICY "select_own_or_superadmin" ON users
    FOR SELECT USING (
        user_id = auth.uid()
        OR is_superadmin = true
    );

-- Users can update only their own profile
CREATE POLICY "update_own" ON users
    FOR UPDATE USING (user_id = auth.uid());

-- Allow user creation during registration
CREATE POLICY "insert_any" ON users
    FOR INSERT WITH CHECK (true);
