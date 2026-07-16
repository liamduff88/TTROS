# Block 3 deterministic fixture end-to-end proof
> Expires: when the capture-to-Needs-Me integration changes. · Last touched: 2026-07-15.

Result: **PASS**.

`python3 tools/aos_capture_fixture_proof.py` ran this local path:

synthetic history delta → immutable capture → replay → rules triage → one
local-stub ambiguous classification → exact client-scope resolution → scoped
fixture evidence → Block 2 scoped Brain loader → scoped disposable search →
real local Graphify fixture selection → existing queue/Needs Me → real local
API → non-accepting review close.

Evidence:

- two raw records; cursor `102`; replay added zero raw records;
- one local classifier invocation with metadata only;
- known client route created `AOS-2026-0092` at `human_review`;
- unresolved route created `AOS-2026-0093` at `needs_input` without content;
- repeat proposer runs returned `created=false` for both;
- `brain_context_used` records note ID `block-3-fixture-client-a`, exact
  synthetic pointer, client scope, pointer route, and content hash;
- local API showed both items in existing Needs Me behavior;
- preview API refused the raw runtime path;
- scoped search API returned one safe row;
- `AOS-2026-0092` closed `blocked` with the precise synthetic-fixture rejection
  receipt; `telegram_reply=null`; no acceptance or external action;
- `AOS-2026-0093` remains `needs_input` as truthful unresolved-scope evidence.

No raw fixture value is reproduced here.

Token usage: no agent invocation.
