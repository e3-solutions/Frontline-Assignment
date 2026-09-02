-- Create loads table for storing negotiation form data
CREATE TABLE IF NOT EXISTS loads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- Create index on org_id for faster lookups
CREATE INDEX idx_loads_org_id ON loads(org_id);

-- Create index on created_at for time-based queries
CREATE INDEX idx_loads_created_at ON loads(created_at DESC);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at on row updates
CREATE TRIGGER update_loads_updated_at
    BEFORE UPDATE ON loads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
