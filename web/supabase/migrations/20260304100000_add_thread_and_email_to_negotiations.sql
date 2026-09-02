-- Add agent_type, thread_id and carrier_contact_email to negotiations

CREATE TYPE agent_type AS ENUM ('email', 'voice');

ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS agent_type agent_type NOT NULL DEFAULT 'voice';
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS thread_id TEXT REFERENCES email_thread(thread_id);
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS carrier_contact_email TEXT;

-- Constraints: email requires thread_id, voice requires call_id
ALTER TABLE negotiations ADD CONSTRAINT chk_email_thread_id
    CHECK (agent_type != 'email' OR thread_id IS NOT NULL);
ALTER TABLE negotiations ADD CONSTRAINT chk_voice_call_id
    CHECK (agent_type != 'voice' OR call_id IS NOT NULL);
