-- Migration: Rename caller_usdot to caller_mc and add mc_not_found enum value
-- MC (Motor Carrier) number is more commonly used for carrier identification

-- Drop the old index
DROP INDEX IF EXISTS idx_calls_caller_usdot;

-- Rename the column
ALTER TABLE calls RENAME COLUMN caller_usdot TO caller_mc;

-- Create new index with updated name
CREATE INDEX idx_calls_caller_mc ON calls(caller_mc);

-- Add the new enum value for mc_not_found
-- Note: Cannot update existing rows in same transaction, old 'usdot_not_found' value remains but unused
ALTER TYPE call_end_reason ADD VALUE IF NOT EXISTS 'mc_not_found';
