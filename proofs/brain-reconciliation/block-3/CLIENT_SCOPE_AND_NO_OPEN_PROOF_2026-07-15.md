# Block 3 client scope and no-open proof
> Expires: when capture identity or Block 2 scope semantics change. · Last touched: 2026-07-15.

Result: **PASS**.

Capture identity matching is a narrow extension of
`context/client_scope_registry.json`; it stores exact synthetic sender/thread
hashes and scope-bound evidence prefixes. It does not create another registry.
`tools/business_brain_scope.py` resolves zero or one enabled scope and returns
explicit states for unresolved, ambiguous, or conflicting hashes.

The 24-test Block 3 suite proves:

- exact synthetic client and global/internal matches;
- unknown identity unresolved;
- duplicate identity ambiguous;
- sender/thread disagreement conflicting;
- client A cannot open client B raw evidence or Brain note;
- client B receives no client A search row or Graphify target;
- unresolved and conflicting fixtures route `needs_input` without opening
  evidence, thread, Brain, search, or Graphify callbacks;
- known global/internal and affirmative Block 2 technical-only routes remain
  explicit.

The real unresolved fixture `AOS-2026-0093` recorded
`unresolved_content_opened=false`. The resolved fixture opened only the
client-scoped evidence callback and one scoped fixture Brain pointer. No
folder-only trust or post-open filtering is used.

Token usage: no agent invocation.
