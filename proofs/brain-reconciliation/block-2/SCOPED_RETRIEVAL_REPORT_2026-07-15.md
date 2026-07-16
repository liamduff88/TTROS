# Scoped retrieval report — Block 2

Status: **PASS**

`tools/business_brain_context.py` implements the hierarchy: explicit pointers; Graphify only for unclear/cross-cutting/relationship-dependent discovery; exact scoped search; direct canonical fallback. Explicit pointers stop the hierarchy. Graphify supplies scoped paths/scores only; the loader separately opens the authoritative vault note through the shared resolver and scope gate.

`brain_context_used` is emitted only after a successful open and contains stable note ID, canonical pointer, declared scope, actual route, and content hash. Candidate results that were not opened are not recorded and bodies are not projected into queue/run provenance.

Real fresh-process proofs after the write:

- pointer PID 3732: `business_brain:index/MEMORY_INDEX.md`, route `pointer`, hash `afcd3d1644453f763158d2b0b59430299abfd560a71e452a4d27e693b36379b7`;
- exact-search PID 3733: same note/hash, route `search`;
- Graphify-assisted PID 3832: same note/hash, route `graphify`.

Technical-only classification is affirmative and records `not_applicable`. Ambiguous work stops as knowledge-sensitive/`needs_input`. Degraded context requires a complete explicit safety contract and cannot waive scope, classification, cross-client, pricing, or commitment failures.

Token usage: no agent invocation
