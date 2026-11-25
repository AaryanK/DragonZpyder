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
