-- Add 'call_transferred' to call_end_reason enum
-- Used when a call is handed off to a human agent via the transfer flow
ALTER TYPE call_end_reason ADD VALUE IF NOT EXISTS 'call_transferred';
