-- Add org_id to calls table for multi-tenant isolation

ALTER TABLE calls ADD COLUMN org_id UUID REFERENCES organizations(id);

CREATE INDEX idx_calls_org_id ON calls(org_id);
