-- Add load and carrier info to email_thread
ALTER TABLE email_thread
    ADD COLUMN load_id UUID REFERENCES loads(id),
    ADD COLUMN carrier_mc TEXT,
    ADD COLUMN carrier_email TEXT;
