# DragonZpyder Identity — Central Account Ownership

DragonZpyder is the identity authority for the personal AI platform and for
business applications such as Operly.

This directory specifies the target contract. It is not yet an active OIDC
identity provider. Keep SSO redirects disabled until a tested issuer, independent
identity database, signing keys, account migration and rollback exist.

## Sign-in flow
1. A user opens DragonZpyder or Operly.
2. The application initiates OIDC Authorization Code + PKCE through
   https://auth.dragonzpyder.xyz.
3. DragonZpyder authenticates the human by password, Google, or Discord.
4. The requesting application redeems the one-time code server-side and verifies
   the token signature, issuer, audience, expiration, nonce, and state.
5. Operly maps the verified (issuer, subject) pair to exactly one local user,
   issues its own host-only session, and checks memberships before business access.
6. SSO alone never grants an organisation role or a business-tool permission.

## Ownership
DragonZpyder owns stable human IDs, passwords, auth-provider identities,
verification, account recovery, MFA, OIDC authorization, revocation and sessions.

Operly owns organisations, roles, memberships, workspace permissions,
business data, scoped tools, business connectors and human approvals.

Do not share parent-domain cookies. The existing __Host- cookie intentionally
cannot be shared across subdomains; this is why the integration uses OIDC.

## Safe migration plan
1. Stand up an isolated DragonZpyder identity database and audited backups.
2. Deploy a maintained OIDC identity implementation with proper key rotation.
3. Migrate verified identity provider subjects with collision detection.
4. Transfer password hashes only through a secured, audited offline backfill
   if the new password verifier supports the exact format, otherwise require
   a password reset. Never expose hashes to browser code or repository files.
5. Verify stable user mapping from Operly user ID to DragonZpyder subject;
   never link identities automatically by matching email addresses.
6. Enable canary single sign-on with SSO flag while preserving legacy login.
7. Test new-user onboarding, disabled accounts, Google/Discord, logout, MFA,
   account recovery, credential revocation and workspace invitations.
8. Expand rollout and finally disable legacy Operly credential issuance.

## Contract
See contracts/oidc-v1.json for operator-controlled issuer and endpoints.
Operly's relying-party adapter stays disabled until the issuer exists and
subject mappings have passed validation.

Acceptance: a human signs into both products, yet cannot enter a business
workspace unless Operly independently verifies membership and permissions.
