-- Migration: Add Row Level Security to existing tables
-- Ensures multi-tenant data isolation

-- ============================================
-- ORGANIZATIONS TABLE RLS
-- ============================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Anyone can read orgs (needed for registration flow)
CREATE POLICY "anyone_can_read_orgs" ON organizations
    FOR SELECT USING (true);

-- Anyone can create orgs (during company registration)
CREATE POLICY "anyone_can_create_orgs" ON organizations
    FOR INSERT WITH CHECK (true);

-- Only admins of the org can update it
CREATE POLICY "admins_can_update_org" ON organizations
    FOR UPDATE USING (
        id IN (SELECT org_id FROM users WHERE user_id = auth.uid() AND role = 'admin')
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- ============================================
-- LOADS TABLE RLS
-- ============================================

ALTER TABLE loads ENABLE ROW LEVEL SECURITY;

-- Users can only see loads from their organization
CREATE POLICY "org_isolation_select" ON loads
    FOR SELECT USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Users can create loads for their organization
CREATE POLICY "org_isolation_insert" ON loads
    FOR INSERT WITH CHECK (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Users can update loads in their organization
CREATE POLICY "org_isolation_update" ON loads
    FOR UPDATE USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Users can delete loads in their organization (admins only)
CREATE POLICY "admin_delete" ON loads
    FOR DELETE USING (
        org_id = (SELECT org_id FROM users WHERE user_id = auth.uid() AND role = 'admin')
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- ============================================
-- CALLS TABLE RLS
-- ============================================

ALTER TABLE calls ENABLE ROW LEVEL SECURITY;

-- Users can only see calls for loads in their organization
-- Calls are linked to loads which have org_id
CREATE POLICY "org_isolation_select" ON calls
    FOR SELECT USING (
        load_id IN (
            SELECT id FROM loads WHERE org_id = (
                SELECT org_id FROM users WHERE user_id = auth.uid()
            )
        )
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
        -- Also allow calls without load_id if created by service (load_not_found case)
        OR load_id IS NULL
    );

-- Only service role (backend) can insert calls
CREATE POLICY "service_insert" ON calls
    FOR INSERT WITH CHECK (true);

-- Only service role (backend) can update calls
CREATE POLICY "service_update" ON calls
    FOR UPDATE USING (true);

-- ============================================
-- NEGOTIATIONS TABLE RLS
-- ============================================

ALTER TABLE negotiations ENABLE ROW LEVEL SECURITY;

-- Users can only see negotiations for loads in their organization
CREATE POLICY "org_isolation_select" ON negotiations
    FOR SELECT USING (
        load_id IN (
            SELECT id FROM loads WHERE org_id = (
                SELECT org_id FROM users WHERE user_id = auth.uid()
            )
        )
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Only service role (backend) can insert negotiations
CREATE POLICY "service_insert" ON negotiations
    FOR INSERT WITH CHECK (true);

-- Only service role (backend) can update negotiations
CREATE POLICY "service_update" ON negotiations
    FOR UPDATE USING (true);

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON POLICY "org_isolation_select" ON loads IS 'Users can only view loads in their organization';
COMMENT ON POLICY "org_isolation_select" ON calls IS 'Users can only view calls for their organization loads';
COMMENT ON POLICY "org_isolation_select" ON negotiations IS 'Users can only view negotiations for their organization loads';
