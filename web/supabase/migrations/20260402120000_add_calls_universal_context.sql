-- Add sanitized universal context capture fields to calls.
--
-- The voice agent stores a redacted snapshot of the final universal context
-- after the call ends so post-call review can inspect the exact LLM context
-- without persisting inline binary payloads.

ALTER TABLE public.calls
    ADD COLUMN IF NOT EXISTS universal_context JSONB,
    ADD COLUMN IF NOT EXISTS universal_context_captured_at TIMESTAMP;

COMMENT ON COLUMN public.calls.universal_context IS
    'Sanitized LLM universal context captured after call completion.';

COMMENT ON COLUMN public.calls.universal_context_captured_at IS
    'Timestamp when universal_context was captured.';
