-- Migration: Add above_max flag and carrier contact fields to negotiations table
-- This allows storing bids that exceed the max rate for potential follow-up

-- Add above_max boolean flag (defaults to false for existing records)
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS above_max BOOLEAN DEFAULT FALSE NOT NULL;

-- Add carrier contact fields for follow-up on above-max bids
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS carrier_contact_name VARCHAR(255);
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS carrier_contact_phone VARCHAR(50);

-- Make agreed_price nullable (above_max entries may store the proposed price, but it's not "agreed")
ALTER TABLE negotiations ALTER COLUMN agreed_price DROP NOT NULL;

-- Add index for querying above_max negotiations
CREATE INDEX IF NOT EXISTS idx_negotiations_above_max ON negotiations(above_max) WHERE above_max = TRUE;
