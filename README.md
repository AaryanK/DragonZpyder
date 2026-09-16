# DragonZpyder

DragonZpyder is the personal client for Operly's governed execution runtime. Operly remains the authority, data boundary, approval system, task worker, and capability executor; DragonZpyder is intentionally thin.

The historical desktop-assistant program stays disabled. The current package contains no shared backend administrator key, provider credential, local browser-control runtime, or independent business/workspace authority.

## Configure

Set an Operly HTTPS endpoint:

```bash
export DRAGONZPYDER_OPERLY_BASE_URL=https://your-operly.example
export DRAGONZPYDER_REQUEST_TIMEOUT_SECONDS=30
```

Remote endpoints must use HTTPS. `http://localhost` is allowed for local development only.

By default the authenticated session cookie jar is stored at `~/.config/dragonzpyder/session.cookies`. Set `DRAGONZPYDER_SESSION_FILE` to choose another local path. Treat this file as an authentication secret; DragonZpyder creates it with restrictive permissions where the platform supports POSIX permissions.

## Personal client

Install without extra runtime dependencies:

```bash
python -m pip install --no-deps .
```

Sign in. The password is prompted securely and is not accepted as a command-line argument:

```bash
dragonzpyder login --email you@example.com
```

If the Operly account initially opens in a Workspace session, DragonZpyder immediately uses Operly's existing `/api/auth/personal-scope` flow to revoke that session and replace it with Personal-only authority. DragonZpyder never asks for a workspace ID.

For an immediate Personal turn:

```bash
dragonzpyder submit "Find an afternoon next week when I am free."
```

The output includes the conversation ID and client request ID. To continue after a clarification:

```bash
dragonzpyder submit --conversation <conversation-id> "Use Tuesday and draft the invitation to Alex."
```

If a network timeout or lost response occurs, retry with the **same** request ID printed by the first attempt. Operly durably scopes that identity to the authenticated Personal principal.

## Durable tasks

Use a durable task when work should survive an API or worker restart, may pause for approval, or should be cancellable while queued/waiting:

```bash
dragonzpyder task "Find an afternoon next week when I am free and prepare the next step."
```

DragonZpyder prints the stable request ID before submission. If the first `202 Accepted` response is lost, repeat the same objective with that exact request ID; Operly returns the same persisted task rather than creating another task or conversation:

```bash
dragonzpyder task --request-id <same-id> "Find an afternoon next week when I am free and prepare the next step."
```

Inspect or cancel the task:

```bash
dragonzpyder task-status <task-id>
dragonzpyder task-cancel <task-id>
```

If a durable task pauses for approval, review the exact proposal with `dragonzpyder approvals`, then approve that specific task step and return execution to Operly's worker:

```bash
dragonzpyder task-approve <task-id> <approval-id>
```

If the approval was already recorded but the client disconnected before the task was requeued:

```bash
dragonzpyder task-resume <task-id> --approval-id <approval-id>
```

DragonZpyder does not execute durable task capabilities itself. It submits, inspects, cancels, and resumes the server-owned task; Operly's durable worker owns leases, authority re-resolution, Kernel execution, retries/reconciliation, and checkpoints. A cancelled task cannot resume. An uncertain external effect is reported as uncertain and must be reconciled before replacement work is submitted.

## Approvals and immediate sends

Review pending approvals before allowing a high-risk immediate action:

```bash
dragonzpyder approvals
```

For an email send, the review shows the exact canonical recipient/subject/body, the server-calculated review hash, and the approval expiry. Approving executes only that exact server-returned contract using the same capability, arguments, request ID, conversation, and approval ID:

```bash
dragonzpyder approve <approval-id>
```

Rejecting performs no action:

```bash
dragonzpyder reject <approval-id>
```

If the approval decision succeeded but the client disconnected before the approved immediate invocation began, resume the already-approved contract instead of approving a new one:

```bash
dragonzpyder resume <approval-id>
```

Operly re-resolves current Personal authority immediately before execution. An edit to the reviewed recipient/body, an expired approval, or revoked permission blocks the action.

For Gmail sends, Operly persists the logical send identity before crossing the provider boundary and uses a deterministic RFC Message-ID. If Gmail acknowledges the message, Operly reports the provider result and attempts read-back verification when the connector scope supports it. If a timeout or disconnect makes delivery ambiguous, DragonZpyder reports **uncertain delivery** and the stable message identity. Do **not** send again just because the HTTP response was lost; the message identity must be reconciled against sent mail first.

Check or revoke the current session:

```bash
dragonzpyder status
dragonzpyder logout
```

`logout` revokes the Operly session server-side and removes the local cookie jar. An expired or revoked session fails as an authentication blocker and requires a fresh login.

## Local validation

```bash
python -m pip install --no-deps .
python -m compileall -q src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_no_secrets.py
```

Do not commit session cookies, tokens, OAuth files, pickle credentials, private keys, provider secrets, or `.env` files.