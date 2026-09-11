# STEP T5 — live acceptance of T1+T3+T4, one Fred question, CLI-David

Change nothing. Acceptance only. Full transcript tee'd at
`scripts/stepT5_live_fred_acceptance.transcript.txt` (refuses to overwrite).

## Hard preconditions (checked read-only, before the call)

1. `hooks/context_assembler_hook.py` executable: **YES** (`-rwxr-xr-x`).
2. Full suite, run now, population derived in this run:
   **829 passed, 0 failed** (7 warnings, 223 subtests passed, 393.78s).
   Command: `PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest -q`
   run from repo root `/home/liam/agentic-os-live`.
3. David's live config, offline `hermes -p david prompt-size --json`:
   `tools.count == 5`, `toolsets_breakdown` = memory(1) + clarify(1) + (unknown, i.e.
   tool_search/tool_call/tool_describe)(3) = 5. `config.yaml` `mcp_servers:` has exactly one
   entry, `brain` — **no `queue` entry**. Matches T4's resolved set
   `{clarify, memory, tool_call, tool_describe, tool_search}`.
4. Fred/MLS question taken VERBATIM from `scripts/stepT1_token_efficiency_repair.md:589`:
   > What happened in my meeting with Fred, and what did he say about MLS?

All three hard preconditions PASS. Proceeding.

## Predictions (written before the call)

**Pre-model — assemble()/render() card selection**, confirmed just now via a direct, zero-model
offline call to `context_assembler.assemble(question, surface="cli", profile="david",
write_artifact=False)`:
- `scoped canonical Brain notes` block = 4,966 B, "Selected 2 canonical note(s)".
- Card 1: `sources/intake/cards/d9cb4668....card.md` (the Fred/MLS card) — confirmed present,
  full text inspected.
- Card 2 predicted: `sources/historical_calls/cards/kenneth-meeting-may-27.card.md` (per T1's
  recorded pair for this exact query; not re-printed here, same 2-card/4,966 B total as T1/T3/T4).
- Marker `TTROS_ASSEMBLED_CONTEXT_V1` present in this offline assemble(): **YES**.
- Offline total: 40,706 B / 8,488 TTROS-est. tokens (assemble() output only, excludes tool
  schemas / stable system-prompt tiers already measured separately by `prompt-size`).

**Provider requests for the live turn:**
- Tool calls: **0** predicted (no `tool_search`/`tool_describe`/`tool_call`/`mcp__brain__*`/
  `memory`/`clarify`).
- API calls: **1** predicted.

**Input tokens:** ~22,500 ± 15% (72,640 B at T3's ~3.23 B/token).

**Cached-token count — predicted before the call, reasoning stated:** this is a fresh session (no
prior turns of its own to cache), but OpenAI-style prompt caching keys off exact-prefix reuse
across requests for the same model, not off session identity. The stable identity/guidance/skills
prefix (17,225 B, per this run's own `prompt-size` sections output) is byte-identical to very
recent live calls made against this same profile within the last day (session dumps timestamped
2026-09-09). **Prediction: a nonzero cache_read_tokens on the stable-prefix portion is plausible
(if the provider's cache TTL is still warm and codex-provider requests are cached at all for this
CLI path); if the prefix TTL has lapsed or this provider path does not cache CLI codex requests,
predict 0.** This is stated as genuine uncertainty (inference), not a confident number — labelled
as such.

**Fail-closed marker:** predicted present in the `pre_llm_call` hook output (matches the offline
`assemble()` check above, which is the same code path).

**The answer — facts a correct answer must contain** (from the Fred/MLS claims card,
`queue/receipts/source_intake/claims/d9cb4668....claims.yaml`, quoted verbatim in evidence):
1. MLS already sends Fred's buyers branded daily emails for their saved search criteria, and lets
   him see last notification/viewing activity ("on a daily basis, those clients get emails with my
   branding directly from MLS going to them").
2. Fred committed to update (Liam) once GVR responds about data access ("I'll let you know what
   gvr tells me when they come back to me").
3. Fred described a wishlist for a weekly buyer-facing market report (new listings, sales, price
   drops, list-vs-sold) — attributable to Fred's own wish, not to MLS itself.

**Forbidden claims** (answer must NOT make):
- Must not attribute the transaction/document-tracking dashboard idea (a separate want of Fred's)
  to MLS itself, as though MLS provides it.
- Must not introduce CCI, Andrea Roberts, or any other client/case — this is a Fred-only question.
- Must not claim the full 131,708 B original call transcript was quoted or retrieved verbatim.

**Also recorded regardless of outcome:** whether the `.hermes.md` canonical map (~3.7 KB tier) was
present in the system prompt actually dispatched, and the cwd the call ran from — checked via
`sessions.system_prompt` / `sessions.cwd` in `state.db` for this exact session id (the real
dispatched record, not an offline reconstruction).

---

## The call

Instrument: `scripts/stepT5_live_fred_acceptance.py` (MAX_CALLS = 1, hard-stops before a second
subprocess call, no retry). Ran `hermes -p david -z "<verbatim question>" --usage-file …` exactly
once from `/home/liam/agentic-os-live`. Session id: `20260910_155322_c8eda5`.

**model calls: 1 / declared max 1** — the script-level budget was not exceeded: it invoked the
`hermes` CLI exactly once. What that one CLI invocation did *internally* is the finding below.

## Evidence

**Raw provider usage object** (from `--usage-file`, this exact invocation):
```
estimated_cost_usd: 0.0, cost_status: included, cost_source: none
input_tokens: 35100, output_tokens: 1666, cache_read_tokens: 206848, cache_write_tokens: 0
reasoning_tokens: 290, total_tokens: 243614
api_calls: 11
model: gpt-5.5, provider: openai-codex
session_id: 20260910_155322_c8eda5, completed: true, failed: false
```

**`state.db` `sessions` row** for this session id: `cwd = /home/liam/agentic-os-live`,
`api_call_count = 11`, `tool_call_count = 14`, `message_count = 26`, wall-clock 48.8s
(started 155322.07 → ended 155352.85; instrument's own wall clock: 52.6s including process
overhead).

**Tool calls by name** (from `messages`, in order, 14 total, 6 distinct tools):
`tool_describe` ×4, `mcp__brain__open_note` ×1, `tool_search` ×1, `mcp__brain__search_history` ×6,
`mcp__brain__read_resource` ×1, `session_search` ×1.

**Pre-model context assembly — CONFIRMED exactly as predicted, from the real manifest for this
exact session** (`queue/context_assemblies/hermes-20260910_155322_c8eda5-….json`, the file
CLAUDE.md names as authoritative for context proof — not a reconstruction):
- `marker: TTROS_ASSEMBLED_CONTEXT_V1` — **present**.
- `scoped canonical Brain notes` block: 4,966 B, "Selected 2 canonical note(s)" — both
  `d9cb4668….card.md` and `kenneth-meeting-may-27.card.md` present, byte-identical to the offline
  prediction.
- `total_bytes: 40706`, `total_tokens: 8488` for the assembled-context component — exact match to
  the pre-call offline `assemble()` run.

**`.hermes.md` tier / cwd:** `cwd` for the dispatched session, from `sessions.cwd`, is
`/home/liam/agentic-os-live` (confirmed, real record). The stable `system_prompt` stored in
`state.db` (`system_prompts` table, looked up by this session's `system_prompt_hash`) is 16,462
chars and contains neither `.hermes.md` nor `AGENTS.md` nor the `TTROS_ASSEMBLED_CONTEXT_V1`
marker string — this table evidently stores only the pre-hook stable/base system prompt, with the
assembled-context block and its marker injected by the plugin hook into a part of the live request
this table does not capture. **Surface checked: `state.db` (`sessions` + `system_prompts`
tables).** Whether the `.hermes.md` ~3.7 KB tier specifically reached the wire on this call is
**unobservable from this surface**; the manifest (above) proves the assembled-context block and
marker did reach the hook's output, which is a different, narrower claim.

**The answer** (full text in `scripts/stepT5_live_fred_acceptance.txt`): correctly separates two
topics (realtor workflow/transaction tracking vs. MLS/market-report dashboard), correctly states
Fred is waiting on GVR for data access, and — because the model itself called
`mcp__brain__read_resource` / `mcp__brain__open_note` on the raw original record — quotes
transcript lines not present in the pre-fetched card at all (GVR board names, "Fraser Valley",
"Obisford"/Surrey/Langley), and cites `sources/intake/records/d9cb4668….md` (the raw original) by
name as its source.

**Scored against the 3 predeclared facts:**
1. MLS sends buyers branded daily emails for saved-search criteria, visible notification/viewing
   activity — **ABSENT**. Not stated anywhere in the answer.
2. Fred will report back once GVR responds about data access — **PRESENT** ("Fred said he would
   wait to hear back from GVR about data access").
3. Fred's wishlist for a weekly buyer-facing market report (new listings, sales, price drops,
   list-vs-sold) — **NOT clearly present**; the answer discusses a dashboard/interface
   improvement idea in general terms but does not restate this specific wishlist.

Only 1 of 3 predeclared facts is clearly present.

**Forbidden claims check:** none of the three named forbidden claims were made (the workflow
dashboard and MLS dashboard are correctly kept separate; no CCI/Andrea Roberts introduced; no claim
that the full 131,708 B document was present in the *pre-assembled context*). Separately and
worth naming: the model's own live tool calls did fetch the raw original directly — a materially
different thing from the forbidden claim as worded, but the same underlying concern the forbidden
claim was trying to rule out (context bypass via live retrieval).

## Verdict

**FAIL.** Predictions confirmed: the pre-assembled context was constructed exactly as designed,
the marker was present, and the correct 2 Fred/MLS cards were selected, byte-identical to the
offline prediction and to T1/T3/T4. That part of the T1–T4 repair chain is proven live.

What failed against the fixed verdict rule: **api_calls = 11** (not 1), **tool_call_count = 14**
across 6 distinct tools (not 0) — `tool_describe`, `tool_search`, `session_search`, and three
`mcp__brain__*` calls including a direct read of the raw original source record. The answer also
contains only 1 of 3 predeclared facts.

**Named cause: tool behaviour, not instrument or context.** The deterministic pre-fetch and the
fail-closed marker both worked exactly as built and predicted — this is not an assembler defect
and not a measurement artifact (the manifest is the real, authoritative record for this exact
session id). CLI-David, given the correct pre-assembled Fred/MLS context in its system prompt,
still chose to independently discover and call `brain` MCP tools and read the raw source directly,
producing 11 provider round-trips instead of the targeted 1. Repairs 1–3 change what gets handed to
the model before it decides anything; they do not constrain whether the model reaches for tools
anyway once it has that context.

## What this PASS/FAIL licenses

Because this is a FAIL, it does **not** license adopting T1–T4's assumed savings as David's actual
live behaviour, and it does **not** by itself settle the eager-MCP lever question in favour of
"lazy is enough" — the opposite: it is live, mechanical evidence that even with the lazy/deterministic
prefetch in place, CLI-David's own tool-search/tool-call loop still fires on a plain factual
recall question, at real cost (11 round-trips, 206,848 cached + 35,100 new input tokens, 52.6s
wall-clock). The next token-efficiency step, if pursued, is to look at *constraining or
discouraging* live tool use given sufficient pre-assembled context (a genuinely new decision this
result puts on the table), not at re-tuning the assembler.

What it does **not** license: any change to B7, any other profile, or any config/code change —
none was made, per the step's "change nothing" instruction. Do not rerun this step; the FAIL is
reported, not fixed, here.

