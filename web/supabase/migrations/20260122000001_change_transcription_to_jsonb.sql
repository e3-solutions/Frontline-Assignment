-- Change transcription column from TEXT to JSONB array format
-- Format: [{role: "caller"|"agent", content: "message", timestamp: "ISO8601"}]

-- Drop the old TEXT column
ALTER TABLE calls DROP COLUMN IF EXISTS transcription;

-- Add as JSONB with proper default
ALTER TABLE calls ADD COLUMN transcription JSONB DEFAULT '[]'::jsonb;

-- Add comment explaining the column
COMMENT ON COLUMN calls.transcription IS 'Structured conversation transcript as JSONB array of {role, content, timestamp} objects';

-- Create index for faster queries on transcription
CREATE INDEX IF NOT EXISTS idx_calls_transcription ON calls USING gin(transcription);
