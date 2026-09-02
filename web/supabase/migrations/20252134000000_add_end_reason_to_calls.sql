-- Create enum type for call end reasons
CREATE TYPE call_end_reason AS ENUM ('abrupt', 'agreement', 'no_agreement', 'error', 'load_not_found');

-- Add end_reason column to calls table
ALTER TABLE calls ADD COLUMN end_reason call_end_reason;

-- Create index for querying by end reason
CREATE INDEX idx_calls_end_reason ON calls(end_reason);
