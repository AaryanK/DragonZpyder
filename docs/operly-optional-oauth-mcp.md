# Operly as an optional OAuth MCP provider

Operly is no longer the authority for DragonZpyder Personal chat. Its existing
Workspace Kernel and MCP authorization remain authoritative for its own
business data. A DragonZpyder Personal user MUST explicitly connect Operly
and an Operly Workspace owner MUST separately authorize the MCP client.

## Registration (operator-controlled, OFF by default)

1. Operly pre-registers the `dragonzpyder` OAuth client using its existing
   `OPERLY_MCP_CLIENTS_JSON` catalog, with an exact redirect:
   `https://www.dragonzpyder.xyz/dz/internal/mcp/oauth/callback`.
   Operly's existing OAuth authorization page requires a live signed-in
   Workspace owner and a separate active `ClientGrant` for this client and
   specific Workspace. No automatic membership or scope assignment occurs.
2. DragonZpyder sets
   `DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL=https://www.dragonzpyder.xyz/dz/internal/mcp/oauth/callback`.
   It configures the existing reviewed `DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON`
   manifest with ONLY independently audited read-only Operly capability IDs:

```json
[
  {
    "provider_id": "operly",
    "mcp_url": "https://operly.dragonzpyder.xyz/mcp",
    "issuer": "https://operly.dragonzpyder.xyz",
    "readonly_tools": ["tasks.list"],
    "scheduled_tools": [],
    "requested_scopes": ["tasks.list", "offline_access"],
    "registration": "pre_registered",
    "client_id": "dragonzpyder",
    "token_endpoint_auth_method": "none",
    "description": "Optional, separately authorized Operly Workspace MCP"
  }
]
```

The example capability ID is illustrative: the actual exposed tool and
scope must be verified through Operly's live registry and OAuth grant tests,
not inferred from the example. **Do not paste unreviewed capability IDs into
production.** A confidential registered client may instead use a sealed
`client_secret_env` and its matching registered authentication method.
Operator config is never exposed to model text or browser JavaScript.

3. Set `DRAGONZPYDER_OPERLY_USER_OAUTH_ENABLED=1` only after host, OAuth
   redirect, PKCE and user-scope tests. Existing general MCP connection
   approval gates and enforced network egress also apply. The browser
   `/dz/internal/mcp/*` routes revalidate first-party identity and CSRF.
4. The user goes to **Connections & tools**, authorizes Operly's own
   workspace prompt, then selects the opaque connection alias for a chat.
   The DragonZpyder model sees only approved generic `search_tools`,
   `describe_tool`, `invoke_tool` handles, never an OAuth credential.
   The manager rechecks ownership, revocation and token freshness at use.
5. Unconnected users simply have no Operly tools. They retain DragonZpyder
   reasoning and other independently connected MCP providers.

## Non-goals and safety gates

This path does NOT automatically enable business mutations, guest workspace
authority, inherited account grants, unattended destructive tools, or full
legacy conversation imports. It is not a way to bypass Operly permissions.
Native Workspace chats from the transitional Operly app use a separate
service-authenticated tool-free DragonZpyder delegate. Providing the exact
user/workspace-scoped MCP grant to that delegate requires a dedicated
review before Workspace actions can be enabled.
