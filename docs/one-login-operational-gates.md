# Production central identity cutover gate: two relying parties

Code migration is not account migration. These steps must be performed with
DB/operator credentials inside an authorized isolated execution context.

1. Record and test a restored backup of Operly's production account,
   auth_identities, federated_identity_maps, workspace membership and
   in-flight sessions. Protect password hashes in a trusted process.
2. Provision an isolated DragonZpyder identity PostgreSQL database/role.
   Apply the reviewed staging-only identity, session, OAuth, password,
   consent and provider-challenge SQL schemas. Staging schemas intentionally
   reject active accounts; an independent security-reviewed production
   activation migration is required.
3. Reconcile canonical Operly UUIDs and verified provider subjects using
   `identity.reconciliation`; do not link on email. Import hashes and
   identity links with `identity.importer` while accounts are pending.
   Cross-check full source and destination subject hashes and workspace
   membership (without publishing any user IDs).
4. Apply `schema_first_party_clients_staging.sql` to register two explicit
   *disabled* clients. After subject/map parity, live permission checks,
   JWT signing-key management, user revocation/replay and browser acceptance
   all pass, enable these two exact clients and activate only approved users.
5. Configure issuer RSA signing key, key id, dedicated grant-hash key, and
   dedicated identity DB URL using secret manager references. Never write
   private keys, password hashes, tokens, or migration credentials into
   source control, agent prompts, browser JavaScript, LangGraph checkpoints
   or Railway plaintext logs.
6. Set DragonZpyder issuer flags only after DB and signing key validation:
   `DRAGONZPYDER_IDENTITY_HTTP_ENABLED=1`,
   `DRAGONZPYDER_IDENTITY_JWKS_ENABLED=1`,
   `DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION=1`.
   Configure matching public key and issuer audience on Operly, then
   `OPERLY_DRAGONZPYDER_SSO_ENABLED=1`,
   `OPERLY_DRAGONZPYDER_SSO_PRODUCTION=1`,
   `OPERLY_DRAGONZPYDER_WEB_SSO_ENABLED=1`.
7. Use a controlled, real HTTPS browser on both domains and confirm separate
   host-only cookies, one issuer login, two client-specific code exchanges,
   correct tenant and Personal permissions, cross-client replay rejection,
   logout/revocation, and disabled-user rejection. Independently verify logs,
   database sessions and the successful workspace readback.
8. Only after no users/roles/schedules were lost, retire legacy Operly
   password login and DragonZpyder's legacy proxy auth flow.

Do not enable live flags from a missing or count-only source inventory.
The existing Railway OAuth connector exposes variable names and deployment
status but no user data, database shell or credential values. This environment
cannot perform/verify a production identity import by itself. Use an
operator-controlled, auditable DB execution path to complete it.
