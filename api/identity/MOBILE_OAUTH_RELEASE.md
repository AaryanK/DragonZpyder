# Mobile provider login release qualification

The native mobile handoff is disabled by default. It is part of DragonZpyder identity, not an Operly authentication adapter. No automatic account creation for Discord; existing provider subject links must be login eligible and active. Explicit Google signup continues to use the existing native signup policy.

## Provider configuration

Use the existing Google Cloud project and Discord application, not a different identity namespace without reviewing provider subject continuity.

- Google: register the **web OAuth client** callback `https://dragonzpyder.xyz/dz/identity/v1/mobile/google/callback`. The same web client ID is the audience of the native Credential Manager Google ID token.
- Discord: register the exact callback `https://dragonzpyder.xyz/dz/identity/v1/mobile/discord/callback`.
- API service: configure `DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID`, `DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_SECRET`, `DRAGONZPYDER_IDENTITY_GOOGLE_MOBILE_REDIRECT_URI`, `DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_ID`, `DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_SECRET`, `DRAGONZPYDER_IDENTITY_DISCORD_MOBILE_REDIRECT_URI`. Keep client secrets in authorized secret storage, never in APKs or source.
- Android Credential Manager: register Android OAuth client for package `xyz.dragonzpyder.android` and the **actual stable signing SHA-1** in the same Google project. For Play distribution use the Play app signing certificate, not just the upload certificate.
- Debug APK #356 certificate SHA-1: `B2:45:D6:1E:0B:E5:34:0E:4A:5F:CB:B0:BD:C4:F7:22:25:73:CD:AF`. This is an observed build fingerprint, not a permanent identity. Hosted CI debug signing can change across runners. Do not register successive ephemeral keys as the production strategy.

Apply `schema_mobile_provider_manual.sql` with the authorized migration role. Verify restricted runtime role, identity import/account links, safe rollback, and authenticated first-party chat before enabling production flags. Set `DRAGONZPYDER_IDENTITY_MOBILE_OAUTH_ENABLED=1` only after qualification; existing production identity and web cutover approvals remain required.

## Acceptance

1. Correct provider consent returns to the Android app via a fixed app callback, with only a short-lived one-time ticket and state.
2. Missing browser binding, wrong state, wrong provider, wrong device verifier, expired ticket, replay and unlinked/disabled subjects fail. No credentials in redirect, logs, checkpoints or client preferences.
3. Google native login and explicit browser retry, existing and new accounts separately, verify issuer, audience, nonce and email. Cancellation does not silently retry. Discord uses exact subject lookup; no linking by email.
4. Test the actual registered Google and Discord applications on a physical phone, with real accounts, both fresh and returning sessions, and app background/process recreation.
5. Test browser handoff across Android browsers, callback interception (PKCE protects redemption; custom scheme may still be intercepted for denial of service), and upgrade to verified HTTPS Android App Links before broad distribution.
6. Verify rate limits at public edge, expiry cleanup, audit events without credentials and production identity permissions. The global pending-attempt cap is not a substitute for per-client abuse protection.

Do not label OAuth fixed until these tests pass against deployed production configuration.
