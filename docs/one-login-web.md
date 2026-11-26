# DragonZpyder Web: central OIDC entry

DragonZpyder Web continues to proxy the existing Operly Personal-data API
behind its own public origin. During migration, the configured **second OIDC
relying party** obtains a separate host-only scoped session for that origin.
The same DragonZpyder issuer session is reused on the Operly relying party.
No shared parent-domain cookies, credentials in JavaScript, untrusted redirects,
or email-based identity linking.

The React account page and Personal app modal expose the identity login link
ONLY when Operly's /api/auth/bootstrap confirms the exact second relying
party is configured. Failure/404 means the link stays hidden. Existing account
sign-in and recovery remain available until real identity and session parity
are independently verified.

Activation requires issuer database import and account activation, two
registered exact-redirect OAuth clients, secure RSA signing configuration,
real HTTPS cross-domain browser tests, restored backups and a rollback plan.
This code does not activate login or migrate any production accounts.
