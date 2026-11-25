# Offline pending identity transfer (operator runbook)

Use this path only after review, green CI and a disposable end-to-end PostgreSQL rehearsal.
The two Railway production networks remain private. No public proxy, new HTTP endpoint,
background job, login flag, or application-level migration privilege is needed.

## Prerequisites
- Back up the source identity tables and target DB securely; verify restore readiness.
- Review the source schema, read-only export role and fresh aggregate counts (all accounts,
  explicit Google auth rows, incompatible non-null password hashes). Review duplicate/orphan
  provider subjects, invalid emails/UUIDs and unsupported credential recovery before approval.
- Use the reviewed manual role scripts in the respective databases:
  `api/identity/schema_export_role_manual.sql` (Operly, role `dz_identity_export`)
  and `api/identity/schema_migration_role_manual.sql` (DragonZpyder, role `dz_identity_migration`).
  These start NOLOGIN; an operator sets distinct SCRAM passwords privately and enables LOGIN
  only for the migration window. The CLI rejects admin, application roles and unexpected
  effective grants. Do not change global Operly permissions to make the check pass.
- Use a dedicated operator process in each respective private network, at the same reviewed
  commit. Do not install privileged DSNs in long-lived web API/worker environment variables.
  Source DSN is OPERLY_IDENTITY_EXPORT_DSN; destination DSN is
  DRAGONZPYDER_IDENTITY_MIGRATION_DSN. The restricted dz_identity_api role cannot import.
  A trusted operator supplies them privately through an approved secret store.
- Use a new random Fernet key (32 random bytes, URL-safe base64 encoded) generated and stored
  privately by the operator. Never pass the key on a command line, in chat, GitHub, logs,
  or with the encrypted package; use the hidden terminal prompt on both sides.
- Work in private directories (mode 0700); no plaintext files. Ensure runner clocks are correct.
- Review the destination activation guard and unused database as required by production_import.
  This runbook does not grant approval to run an actual production migration.

## Export
From the API directory on the source-side migration runner, substitute independently reviewed
aggregate counts for A, G and R (not literal placeholders):
```sh
python -m identity.offline_transfer export --package /private/identity.enc \
  --expected-accounts A --expected-google-links G --expected-unsupported-passwords R \
  --approve-export
```
The tool reads a repeatable-read, read-only snapshot, reuses the existing reconciliation,
and writes an owner-only authenticated encrypted package. Output is counts and ciphertext
SHA-256 only. R must match the exact number of incompatible hashes; they are omitted
from the destination, not changed in Operly. Zero is strict. Supported hashes are retained.
All affected identities require an independently verified recovery/linking path before activation.
No external channel or Discord identities are made native login credentials.

Transfer the ciphertext using an authorized operator-controlled file transfer. Do not put
it in chat, Git, public storage or the same channel as the key. Verify the digest through
an independent trusted channel. On the target runner set file permissions to 0600
and verify the owner. Packages expire after 24 hours; re-export if expired.

## Import
From the API directory on the destination-side migration runner:
```sh
DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT=1 python -m identity.offline_transfer import \
  --package /private/identity.enc --expected-sha256 REVIEWED_CIPHERTEXT_DIGEST \
  --expected-accounts A --expected-google-links G --expected-unsupported-passwords R \
  --approve-pending-import
```
The CLI refuses mismatched digest, wrong key, expired package, changed inventory and
nonempty destination. It reuses the existing atomic pending-only import. Expect exactly
A accounts, G links, zero active accounts. Existing source records remain intact.
Immediately disable LOGIN for both temporary roles and terminate any remaining sessions
using the verified role names. Review role dependencies and revoke the temporary grants/policies
before dropping either role; never use a broad DROP OWNED against an unverified database.
Remove transfer files and retire the one-use transfer key according to your security policy
after retaining the required protected backup and aggregate audit receipt.

## Before activation
An authenticated package and counts prove transfer integrity, not source freshness,
individual credential validity or recovery eligibility. Reconcile against live source
under a reviewed freeze/delta procedure. Do not remove the imported-account activation
guard or enable native login. Verify account recovery, immutable user-ID mapping,
conversation migration, and real two-account Operly workspace authorization first.
