# Opt-in DragonZpyder Personal memory storage consolidation

Reuse the existing agent PostgreSQL service only when the operator independently
sets DRAGONZPYDER_MEM0_USE_AGENT_DATABASE=1 and
DRAGONZPYDER_MEM0_AGENT_DB_APPROVED=1, and does not also set a dedicated
memory DB URL. Provision pgvector, dedicated schema/role and tested backups
before activating. Existing explicit memory write consent remains mandatory.

This feature does NOT migrate Operly memories, conversation histories,
connected-provider credentials or artifacts, nor does it grant the LLM any
memory tools automatically. A separate per-user migration with canonical
IDs, scope consent, provenance, deletion and digest verification is still
required. The Operly computer runner remains workspace-scoped: a Personal
computer capability requires its own reviewed authorization policy.
No production database setting is changed by this commit.
