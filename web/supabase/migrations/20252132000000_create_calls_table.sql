CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    load_id UUID NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
    negotiation_result UUID REFERENCES negotiations(id) ON DELETE SET NULL,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    caller_number TEXT NOT NULL,
    caller_country_code TEXT NOT NULL,
    initiated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_calls_load_id ON calls(load_id);
CREATE INDEX idx_calls_negotiation_result ON calls(negotiation_result);

CREATE TRIGGER update_calls_updated_at
    BEFORE UPDATE ON calls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE negotiations ADD COLUMN call_id UUID REFERENCES calls(id) ON DELETE SET NULL;
CREATE INDEX idx_negotiations_call_id ON negotiations(call_id);
