# TOKEN CONTROL
> Revisit: on provider usage-schema, pricing, or model-runner change. · Last touched: 2026-08-04.

- The one cost/effort dial is `light|standard|heavy`; precedence is scoped
  override → global operator config → documented `standard` default.
- The one breaker is 500,000 canonical tokens per work item or sticky session.
- 250,000 and 400,000 are visible informational events only. At 500,000 the
  completed invocation is recorded and the next invocation is blocked.
- Provider input plus provider output is the canonical fuse total. Cached input
  is visible and priced separately but never added to input twice. Reasoning is
  a labelled output subset.
- Missing/corrupt usage is unknown, never zero, and fails closed.
- Scoped override/reset changes only fuse state; it grants no action permission.
- Context Assembler completeness and Brain access are independent of the dial.
- Native automatic compaction remains session hygiene and preserves required
  task context.

Full mechanics: `context/TOKEN_POLICY.md`.
