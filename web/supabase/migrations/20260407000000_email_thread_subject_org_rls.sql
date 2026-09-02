-- Migration: Add subject + org_id to email_thread, enable RLS on email tables
--
-- Why:
--   1. subject was never persisted — frontend needs it for display
--   2. org_id is required for RLS isolation (email_thread had none)
--   3. email_thread and email_interactions had no RLS at all — any
--      authenticated user could read all tenants' email data

-- ============================================
-- 1. ADD subject AND org_id TO email_thread
-- ============================================

ALTER TABLE email_thread
    ADD COLUMN IF NOT EXISTS subject TEXT,
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);

-- Backfill org_id for existing threads from their linked load
UPDATE email_thread et
SET org_id = l.org_id
FROM loads l
WHERE et.load_id = l.id
  AND et.org_id IS NULL;

-- ============================================
-- 2. RLS ON email_thread
-- ============================================

ALTER TABLE email_thread ENABLE ROW LEVEL SECURITY;

-- Authenticated users see only their org's threads
-- Superadmins see all
-- Threads with no org_id (edge case: load was deleted) are hidden
CREATE POLICY "org_isolation_select" ON email_thread
    FOR SELECT USING (
        org_id = auth_user_org_id()
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Backend (service role) can insert and update freely
DROP POLICY IF EXISTS "service_insert" ON email_thread;
CREATE POLICY "service_insert" ON email_thread
    FOR INSERT TO service_role
    WITH CHECK (true);

DROP POLICY IF EXISTS "service_update" ON email_thread;
CREATE POLICY "service_update" ON email_thread
    FOR UPDATE TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================
-- 3. RLS ON email_interactions
-- ============================================

ALTER TABLE email_interactions ENABLE ROW LEVEL SECURITY;

-- Interactions are isolated via their parent thread's org_id
CREATE POLICY "org_isolation_select" ON email_interactions
    FOR SELECT USING (
        thread_id IN (
            SELECT thread_id FROM email_thread
            WHERE org_id = auth_user_org_id()
        )
        OR EXISTS (SELECT 1 FROM users WHERE user_id = auth.uid() AND is_superadmin = true)
    );

-- Backend (service role) can insert and update freely
DROP POLICY IF EXISTS "service_insert" ON email_interactions;
CREATE POLICY "service_insert" ON email_interactions
    FOR INSERT TO service_role
    WITH CHECK (true);

DROP POLICY IF EXISTS "service_update" ON email_interactions;
CREATE POLICY "service_update" ON email_interactions
    FOR UPDATE TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON COLUMN email_thread.subject IS 'Email subject line captured at thread creation';
COMMENT ON COLUMN email_thread.org_id IS 'Organization that owns this thread (for RLS isolation)';
COMMENT ON POLICY "org_isolation_select" ON email_thread IS 'Users can only view email threads belonging to their organization';
COMMENT ON POLICY "org_isolation_select" ON email_interactions IS 'Users can only view interactions for their organization threads';
