-- Apply with the identity migration role, after existing identity bootstrap.
BEGIN;
CREATE TABLE IF NOT EXISTS public.identity_mobile_provider_attempts (
    state_hash text PRIMARY KEY,
    app_state text NOT NULL,
    browser_hash text NOT NULL,
    challenge text NOT NULL CHECK (length(challenge)=43),
    provider text NOT NULL CHECK (provider IN ('google','discord')),
    nonce text NOT NULL,
    register boolean NOT NULL DEFAULT false,
    expires_at timestamptz NOT NULL,
    callback_claimed_at timestamptz,
    ticket_hash text UNIQUE,
    subject text REFERENCES public.identity_accounts(subject),
    redeemed_at timestamptz
);
CREATE INDEX IF NOT EXISTS identity_mobile_provider_expiry ON public.identity_mobile_provider_attempts(expires_at);
REVOKE ALL ON public.identity_mobile_provider_attempts FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.identity_mobile_provider_attempts TO dz_identity_api;
COMMIT;
