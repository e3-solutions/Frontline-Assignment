-- COR-883: load-scoped transfer routing must be present on every load row.
-- Populate NULL transfer routing rows before running this migration.
-- There is no runtime fallback to a global env phone number after COR-883.

UPDATE public.loads
SET transfer_call_to = NULL
WHERE transfer_call_to IS NOT NULL AND btrim(transfer_call_to) = '';

UPDATE public.loads
SET transfer_country_code = NULL
WHERE transfer_country_code IS NOT NULL AND btrim(transfer_country_code) = '';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.loads
        WHERE transfer_call_to IS NULL
           OR transfer_country_code IS NULL
    ) THEN
        RAISE EXCEPTION 'Cannot enforce required transfer routing on public.loads until backfill completes';
    END IF;
END;
$$;

ALTER TABLE public.loads
    ALTER COLUMN transfer_call_to SET NOT NULL,
    ALTER COLUMN transfer_country_code SET NOT NULL;
