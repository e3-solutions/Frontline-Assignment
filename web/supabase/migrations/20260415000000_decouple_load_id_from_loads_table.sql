-- Decouple load_id from the Supabase `loads` table.
--
-- Load records now live in Salesforce (rtms__Load__c) — see
-- docs/SALESFORCE_INTEGRATION.md. After this migration, the `load_id`
-- columns on negotiations, calls, and email_thread store Salesforce
-- 18-char Ids (e.g. a1GTQ000008EiIE2A0) instead of Supabase UUIDs.
--
-- The `loads` table itself is left in place so historical rows remain
-- queryable, but the FK relationships are severed and the columns are
-- retyped to TEXT.

BEGIN;

-- negotiations.load_id
ALTER TABLE negotiations DROP CONSTRAINT IF EXISTS negotiations_load_id_fkey;
ALTER TABLE negotiations ALTER COLUMN load_id TYPE TEXT USING load_id::TEXT;
COMMENT ON COLUMN negotiations.load_id IS 'Salesforce rtms__Load__c.Id (18-char). Previously a UUID FK to loads(id).';

-- calls.load_id
ALTER TABLE calls DROP CONSTRAINT IF EXISTS calls_load_id_fkey;
ALTER TABLE calls ALTER COLUMN load_id TYPE TEXT USING load_id::TEXT;
COMMENT ON COLUMN calls.load_id IS 'Salesforce rtms__Load__c.Id (18-char). Previously a UUID FK to loads(id).';

-- email_thread.load_id
ALTER TABLE email_thread DROP CONSTRAINT IF EXISTS email_thread_load_id_fkey;
ALTER TABLE email_thread ALTER COLUMN load_id TYPE TEXT USING load_id::TEXT;
COMMENT ON COLUMN email_thread.load_id IS 'Salesforce rtms__Load__c.Id (18-char). Previously a UUID FK to loads(id).';

COMMIT;
