# Universal MCP runtime — incremental consolidation

DragonZpyder uses the upstream LangChain MCP adapter and one provider-neutral
broker, not a custom implementation of JSON-RPC. The existing explicit
Operly delegation stays in place; the experimental reviewed-server adapter
now uses the same broker rather than maintaining independent SDK discovery.

## One invocation contract

Trusted service code supplies an ephemeral `McpGrant`: provider/connection
identifier, reviewed endpoint, authority headers and exact granted capability
IDs. The model never chooses an endpoint or supplies a token. In the new
progressive catalog, the model sees three tools:

- `search_tools(query, limit)`: bounded keyword search of authorized names and
  provider descriptions. No server request; no global credentials.
- `describe_tool(provider_id, tool_name)`: retrieve just the selected exact
  tool's advertised input schema and a SHA-256 schema identity.
- `invoke_tool(provider_id, tool_name, arguments, schema_sha256)`: rediscover,
  verify the exact schema, validate arguments, invoke the SDK adapter, reject
  unsuccessful/approval-pending results, and return a hashed receipt.

This is **read-only** on independently reviewed capabilities. The receipt
proves a returned invocation with no recognized failure envelope, not the
truth of the provider's payload or completion of the user's objective.
Returned data is untrusted. Unknown or ambiguous behavior is not an
independently verified effect. Output larger than 32 KB is explicitly marked
truncated and still hashed; there is no new durable artifact store.

Direct Operly aliases and signed scheduled reads remain compatible. Existing
interactive Operly calls still use direct SDK-adapted tools, and its existing
approval flows are unchanged. The new generic catalog and scheduled broker
invoke use the same request primitive; there is no provider-specific switch
in the new runtime. The generic catalog resolves exact provider/tool pairs
even if their legacy model aliases normalize to the same name.

## Configuration-only reviewed public provider onboarding

Example **fictional** registry (not real endpoints):

```json
[
  {
    "provider_id": "archive",
    "url": "https://archive.example.com/mcp",
    "description": "Search public document archives",
    "readonly_tools": ["search", "get_document"]
  },
  {
    "provider_id": "library",
    "url": "https://library.example.com/mcp",
    "description": "Search public library metadata",
    "readonly_tools": ["lookup"]
  }
]
```

Store the manifest in trusted deployment configuration as
`DRAGONZPYDER_MCP_PUBLIC_CATALOG_JSON`. Reviewed HTTPS hosts must be separately
declared in `DRAGONZPYDER_MCP_TRUSTED_HOSTS`. The new Personal catalog is off
unless all three independent gates are enabled:

- DRAGONZPYDER_MCP_PERSONAL_PUBLIC_CATALOG_ENABLED=1
- DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED=1
- DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED=1

The last flag is an operator assertion; verify actual DNS/IP/redirect egress
enforcement before activation. Never register an endpoint based on a model's
instruction or third-party prompt. Tool annotations are not permission grants.
Review data disclosure as well as write risk (read tools can transmit user
arguments). Do not enable these gates in production based solely on CI.

The current deployment manifest is bounded to 1000 providers, 40 explicitly
reviewed capabilities per provider and 500 KB; the run catalog bounds search
results to 20. This is a first scale-safe interface, not a production index
for an unlimited global ecosystem. Search uses configured provider and tool
names, not an embedding index of full schema descriptions. Descriptions
and live schemas are fetched on demand. It cannot auto-authorize new tools.

## Acceptance and remaining scope

Tests exercise a thousand-entry catalog without eager network discovery,
two independent synthetic SDK providers with the same tool name, ambiguous
alias resolution, exact schema drift, authorization denial, structured
failure envelopes, and the disabled-by-default manifest gate. These are
offline contract tests, not live external MCP provider execution.

Next steps before broad external integrations:
1. Persistent verified provider metadata registry and user connection IDs,
   OAuth/OIDC/other supported auth lifecycle, credential isolation and live
   revocation. Multiple private accounts for one provider are not implemented.
2. Binding shared invocation/approval/effect-reconciliation middleware to
   direct interactive calls; authenticated mutations remain on existing
   provider-specific approval paths.
3. Renew user grants on every Hatchet wake and resume actual LangGraph agent
   objectives using this catalog, rather than expanding specialized read DAGs.
4. Add semantic tool search, negotiated resources/prompts and secure provider
   egress. Real provider conformance tests, credential isolation and held-out
   cross-provider workflows must pass before general production exposure.

No new services or databases. No new model calls needed for these tests.
