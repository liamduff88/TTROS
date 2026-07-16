# Client-scope registry report — Block 2

Status: **PASS**

The canonical authority is `context/client_scope_registry.json`, validated by `context/client_scope_registry.schema.json` and enforced by `tools/business_brain_scope.py`. It is durable Agentic OS configuration, not capture state or a parallel database.

The registry uses exact scope IDs and defaults to deny. `global` is the only enabled live scope and enumerates 18 permitted canonical Business Brain pointers, the corresponding search identities, the `ttros-business-brain` Graphify namespace/targets, and explicit fixture evidence identities. The protected-client pointer is recorded as denied metadata and its scope is disabled; its source was not opened. Tests use `client-a`, `client-b`, and `global` synthetic fixtures rather than live client facts.

Every boundary resolves the declared scope, validates the exact source identity, and only then opens/queries/returns content. No folder-name, tag, title, free text, or model inference participates in authorization.

Covered gates: pointer resolution, direct note loading, SQL search, Graphify target return, evidence fixtures, context-receipt validation, and promotion targets.

Token usage: no agent invocation
