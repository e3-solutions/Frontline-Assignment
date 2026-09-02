-- Add 'bid_placed' to call_end_reason enum
-- Used when we store an above-max bid for potential follow-up (instead of no_agreement)
ALTER TYPE call_end_reason ADD VALUE IF NOT EXISTS 'bid_placed';
