-- Add transcription column to calls table for storing human-readable transcript
ALTER TABLE calls ADD COLUMN IF NOT EXISTS transcription TEXT;

-- Add comment explaining the column
COMMENT ON COLUMN calls.transcription IS 'Human-readable conversation transcript in format "Role: message"';
