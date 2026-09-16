# DragonZpyder

DragonZpyder is the personal client for Operly's governed execution runtime. Operly remains the authority, data boundary, approval system, and capability executor; DragonZpyder is intentionally thin.

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

Submit a task:

```bash
dragonzpyder submit "Find an afternoon next week when I am free."
```

The output includes the conversation ID and client request ID. To continue after a clarification:

```bash
dragonzpyder submit --conversation <conversation-id> "Use Tuesday and draft the invitation to Alex."
```

If a network timeout or lost response occurs, retry with the **same** request ID printed by the first attempt:

```bash
dragonzpyder submit --request-id <same-id> "Find an afternoon next week when I am free."
```

Operly durably scopes this ID to the authenticated Personal principal. An identical completed retry replays the stored result; a changed payload under the same ID is rejected; an unresolved request is reported as in progress rather than blindly duplicated.

Review pending approvals and decide them through Operly's existing Personal approval endpoints:

```bash
dragonzpyder approvals
dragonzpyder approve <approval-id>
dragonzpyder reject <approval-id>
```

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
