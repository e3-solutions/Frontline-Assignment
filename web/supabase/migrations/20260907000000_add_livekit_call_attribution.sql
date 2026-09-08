-- Attribute calls to their telephony provider without rewriting historical
-- Daily identifiers. Existing rows remain explicitly Daily-owned.
alter table public.calls
    add column if not exists telephony_provider text not null default 'daily',
    add column if not exists provider_call_id text;

alter table public.calls
    drop constraint if exists calls_telephony_provider_check;

alter table public.calls
    add constraint calls_telephony_provider_check
    check (telephony_provider in ('daily', 'livekit'));

create index if not exists calls_provider_call_id_idx
    on public.calls (telephony_provider, provider_call_id)
    where provider_call_id is not null;

comment on column public.calls.telephony_provider is
    'Voice transport that owns this call record.';

comment on column public.calls.provider_call_id is
    'Opaque provider call identifier; do not use it as a customer-visible ID.';
