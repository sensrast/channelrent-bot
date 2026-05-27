-- Add per-channel auto-accept-requests toggle
ALTER TABLE channels
  ADD COLUMN IF NOT EXISTS auto_accept_requests BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_channels_auto_accept ON channels(auto_accept_requests);
