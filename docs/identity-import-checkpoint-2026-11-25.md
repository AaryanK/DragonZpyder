# Production identity import checkpoint — 2026-11-25

Operator-observed production evidence: 69 pending accounts, 69 preserved immutable
Operly IDs, 12 Google login bindings, 11 non-null password hashes, zero active
imported accounts and zero enabled OAuth clients. The encrypted transfer completed
successfully. The operator reports disabling temporary source/export and
destination/import logins and clearing their passwords. No live native sign-in
or federation cutover is claimed.

The local protected backup checksum matched and a disposable restore reproduced
all 69 accounts and the login/channel inventory. Operly-specific triggers were
excluded from that isolated rehearsal because their function dependencies were
outside the three-table dump; this does not prove a full application restore.
The temporary Railway database and its volume were deleted.

## Pre-activation gates

1. Remove transient encrypted transfer packages from both application containers
   and the workstation once approved retention requirements are met. Preserve the
   separately protected source and destination backups. Retire the transfer key.
2. Reconcile under a reviewed write freeze or delta procedure. Use
   pending_reconciliation.snapshot_receipt with the same separately generated
   32-byte random key in trusted source and destination operator processes.
   Read source with production_import.read_source_snapshot and destination with
   pending_reconciliation.read_pending_target, each in a private network.
   Compare only aggregate HMAC receipts via compare_receipts. Never grant the
   temporary insertion role access to password hashes. A receipt mismatch or
   inventory drift blocks activation; no overwrite or automatic reconciliation.
   This checks only the imported fields; source-only channel identities remain
   Operly-owned. For snapshots with omitted unsupported hashes, separately review
   source hash compatibility and changes; no omissions were reported for this
   production import. The helper has an operator-only CLI; see below.
3. Establish verified per-account proof and operator-approved activation, not
   mass activation. The 18 candidate password/Google users are not yet proven;
   51 lack either candidate path. Recovery must require fresh authorized proof
   of the immutable source subject (or independently reviewed recovery),
   never mere email matching or a linked Discord channel. Keep Operly login
   functional while recovery and federation are being implemented.
4. Do not apply schema_import_activation_review.sql or enable native auth yet.
   Require two-account A/B sign-in, workspace membership isolation, revocation,
   rollback, recovery, and new registration tests. Verify conversation history
   migration and routing before retiring the legacy harness.

These are checkpoints based on operator output, not an independent production
database read by the repository CI runner. No production credentials, account
rows, password hashes or transfer keys belong in this document.


## Read-only operator reconciliation

Run the reviewed revision on each private network using a short-lived operator
process. On the source, use the existing scoped export DSN for a separately
authorized short window; revoke it immediately afterward. On the target,
reuse the restricted identity API DSN. Do not enable identity HTTP endpoints.

Generate a fresh independent random 32-byte key, represented as 64 hexadecimal
characters, in a private local session. Enter the same key at both hidden
prompts. Never reuse or disclose the transfer key or this reconciliation key.

From the API directory on the reviewed revision:

```sh
python -m identity.pending_reconciliation source --expected-accounts 69 --expected-google-links 12 --approve-read-only
python -m identity.pending_reconciliation target --expected-accounts 69 --expected-google-links 12 --approve-read-only
```

The first command is for the source runner only; the second is for the target
runner only. Compare the resulting aggregate HMAC receipts privately:

```sh
python -m identity.pending_reconciliation compare SOURCE_RECEIPT TARGET_RECEIPT
```

A match is evidence that the captured snapshots agree on imported fields. It
is not proof of a write freeze, of successful authentication, or of recovery
eligibility. Confirm source freshness at cutover; a mismatch is a stop condition.


## Individual activation and proof collection (review only)

The revised `schema_import_activation_review.sql` replaces the blanket
pending-only fence with a per-subject foreign-key-backed approval receipt.
Installing it alone activates zero accounts. Approval references a fresh
stored proof, not a caller-supplied method or timestamp. The API can insert
proof records after credential verification but cannot set the database
proof time, update/delete proof records, create approval receipts or execute
the approval function. This trusts the identity verifier process; it is
not protection against a compromised verifier with its database credentials.
No agent/MCP tool may invoke these proof paths.

`pending_proof_http.py` adds origin-checked, independently gated proof
collection routes. Both `DRAGONZPYDER_IMPORT_PROOF_ENABLED` and, in production,
`DRAGONZPYDER_IMPORT_PROOF_ALLOW_PRODUCTION` default off. The endpoints never
create sessions, grant access or activate accounts. Password proof uses
the same persistent attempt budget as login and requires the source's
verified-email condition. Google proof uses the prelinked exact subject
and a distinct one-time browser-bound nonce challenge. A proof reference
is not a bearer credential or an activation grant.

The operator-only `approve_imported_identity(subject, proof_id)` function
checks source-active status, immutable subject, pending state, credential
candidate and the 15-minute DB-generated proof window. It records the
same proof method/time and operator identity atomically with activation.
No legacy-session or Discord-channel proof is currently accepted.
Installing the schema or enabling proof collection in production is NOT
authorized by this document. Before enabling, require fresh source
reconciliation, independent review, network-level abuse controls,
a real browser UI, operator approval and two-account live isolation tests.

## Recovery of credentialless accounts

Operly's existing `/api/auth/forgot-password` checks that the account is
active and its email has been verified; it can issue a recovery challenge
even when no password hash is present. Its reset handler verifies the
challenge, installs a new hash and revokes existing sessions. Reuse this
source-owned recovery path while Operly remains the authentication owner.
A reset changes the source snapshot, so a controlled pending-only delta
reconciliation is required before that account can use the imported
password proof. Do not copy plaintext passwords or auto-link by email.
Accounts lacking verified email require an independently verified source
credential or a separately reviewed recovery process. Preserve their IDs
and data while pending. The previous count of 51 is based on absent
password/Google links, not a verified recovery-method inventory.

Run `source_recovery_inventory_manual.sql` on the source to identify the
verified/unverified email split and explicit Discord login bindings.
Only aggregate counts are returned. An actual source write freeze or
approved delta protocol is required before activating any imported account.

## Conversation migration boundary

Operly's agent_chat_conversations model distinguishes personal ownership
(owner_user_id, no workspace_id) from workspace ownership (workspace_id,
no owner_user_id). Only personal rows may be migrated to DragonZpyder's
first-party conversation index. Never export business/workspace histories
under a personal account. Both delegated Personal and first-party chat
use DragonZpyder's existing personal_thread(user_id, conversation_id)
checkpoint key. Audit the existing checkpoint before importing/replaying
messages: do not duplicate the history or import tool leases, pending
approvals, attachments, or connector secrets into another authority.
Conversation export/import and legacy-only history recovery remain separate
engineering work; no live conversation migration has been executed.


### Operator-observed recovery inventory (2026-11-25)

The source query reported 69 accounts: 17 active native candidates
(Google or password with verified email), 51 active accounts with verified
email but no password/Google link, and one requiring other verification.
These are candidate paths, not completed individual proofs or successful
email deliveries. No users were notified or reset.

`recovery_delta.py` permits a strictly reviewed null-to-hash addition from
a new encrypted source export, preserving the entire set of immutable IDs,
Google bindings and all other imported fields. The separate temporary
`dz_identity_recovery_sync` role has only the read permissions needed
for this comparison and RLS-scoped UPDATE(password_hash) on an active-source,
verified-email pending import with a NULL old password. It cannot activate
accounts or replace passwords. Provision the role only when a real recovery
addition must be synchronized, and retire it afterward. A mismatch in any
other field or count is a stop condition. The current implementation only
operates under the original global pending fence: it is not a continuous
post-activation credential bridge. Do not use this to force mass password
resets or ask users to disclose credentials. A separately reviewed native
recovery or per-account authority handoff is needed for staggered cutover.
