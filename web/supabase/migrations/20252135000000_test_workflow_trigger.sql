-- Test migration to trigger Supabase preview branch workflow
-- This adds a comment to the loads table

COMMENT ON TABLE loads IS 'Stores negotiation form data and load information';
COMMENT ON COLUMN loads.id IS 'Unique identifier for each load';
COMMENT ON COLUMN loads.org_id IS 'Organization identifier that owns this load';
COMMENT ON COLUMN loads.data IS 'JSON data containing all load details';
COMMENT ON COLUMN loads.created_at IS 'Timestamp when the load was created';
COMMENT ON COLUMN loads.updated_at IS 'Timestamp when the load was last updated';

