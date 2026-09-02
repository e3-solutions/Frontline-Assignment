-- Add dedicated recording_url column to calls table
ALTER TABLE calls ADD COLUMN IF NOT EXISTS recording_url TEXT;

-- Migrate existing audio_url from result JSONB to the new column
UPDATE calls
SET recording_url = result->>'audio_url'
WHERE result->>'audio_url' IS NOT NULL;

-- Create index for faster queries on recording_url
CREATE INDEX IF NOT EXISTS idx_calls_recording_url ON calls(recording_url) WHERE recording_url IS NOT NULL;
