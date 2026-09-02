-- Add load_id column to loads table for easier querying by load ID
ALTER TABLE loads ADD COLUMN load_id TEXT;

-- Create index on load_id for faster lookups
CREATE INDEX idx_loads_load_id ON loads(load_id);
