-- Add sent_email_id to track the email ID of bot responses
ALTER TABLE email_interactions ADD COLUMN sent_email_id TEXT;
