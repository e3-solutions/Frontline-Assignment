-- Make load_id nullable to allow call records without associated loads
-- (e.g., calls that end early due to USDOT verification failure)
ALTER TABLE calls ALTER COLUMN load_id DROP NOT NULL;
