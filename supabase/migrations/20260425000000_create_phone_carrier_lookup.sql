-- phone_carrier_lookup
--
-- KCH-owned cache mapping caller phone numbers (E.164) to a verified carrier
-- identity, scoped per organization. Populated by the voice-agent's
-- verify_carrier tool handler when an unknown-phone caller successfully
-- verifies an MC. Read by phone_verification.resolve_caller_identity in
-- parallel with the Highway phone_search lookup.
--
-- Conflict policy on upsert: overwrite the existing row with the latest
-- verified MC, bump last_verified_at. (History is not retained.)

CREATE TABLE IF NOT EXISTS phone_carrier_lookup (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Logical FK to organizations(id) — not enforced at the DB layer so the
    -- migration is portable across Supabase environments where `organizations`
    -- may live outside this migration tree (e.g. dashboard-managed in prod,
    -- absent in fresh preview branches). Application code validates org
    -- membership via the existing phone_numbers join in db_operations.py.
    -- Production has an organizations table + RLS already configured; the
    -- service-role client used by the voice-agent bypasses RLS by design.
    org_id UUID NOT NULL,
    phone_e164 TEXT NOT NULL,
    mc_number TEXT NOT NULL,
    carrier_name TEXT,
    dot_number TEXT,
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT phone_carrier_lookup_phone_e164_format
        CHECK (phone_e164 ~ '^\+[0-9]{7,15}$')
);

-- One verified MC per (org, phone). Upserts target this constraint.
CREATE UNIQUE INDEX IF NOT EXISTS phone_carrier_lookup_org_phone_uidx
    ON phone_carrier_lookup (org_id, phone_e164);

-- Cheap secondary index for ad-hoc lookups by phone across orgs (debugging,
-- analytics). Not used by the bot's hot path.
CREATE INDEX IF NOT EXISTS phone_carrier_lookup_phone_idx
    ON phone_carrier_lookup (phone_e164);

-- Auto-bump updated_at on row update.
CREATE OR REPLACE FUNCTION phone_carrier_lookup_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS phone_carrier_lookup_updated_at ON phone_carrier_lookup;
CREATE TRIGGER phone_carrier_lookup_updated_at
    BEFORE UPDATE ON phone_carrier_lookup
    FOR EACH ROW EXECUTE FUNCTION phone_carrier_lookup_set_updated_at();
