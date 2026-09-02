-- Migration: Add webhook subscription tracking to email_tenant

ALTER TABLE email_tenant
ADD COLUMN IF NOT EXISTS inbox_subscription_id TEXT,
ADD COLUMN IF NOT EXISTS sentitems_subscription_id TEXT,
ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMPTZ;
