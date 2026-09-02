CREATE TABLE IF NOT EXISTS negotiations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    load_id UUID NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
    agreed_price NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

CREATE INDEX idx_negotiations_load_id ON negotiations(load_id);

CREATE TRIGGER update_negotiations_updated_at
    BEFORE UPDATE ON negotiations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
