# STEP T6 — finding and repairing why T5's one turn became eleven

Reads `scripts/stepT5_live_fred_acceptance.md` as given; T1–T4 not re-derived. Transcript tee'd at
`scripts/stepT6_live_overretrieval_repair.transcript.txt` (refuses to overwrite).

**Note on starting state:** at the start of this step, `/home/liam/ttros_backups/stepT6_2026-09-10/`
already existed (`PREIMAGE.sha256`, `context_assembler.py.PREIMAGE`,
`david_config.yaml.PREIMAGE`, all timestamped 16:34, ~40 min after T5's 15:53 live call), and both
`tools/context_assembler.py` and `/home/liam/.hermes/profiles/david/config.yaml` already carried
edits matching this step's C1/C2 spec, including a code comment literally reading
"F-TOOLOVERREACH-1 (Step T6, 2026-09-10)". Per the standing rule to investigate unexpected state
before acting on it: preimage hashes were verified to match the `.PREIMAGE` copies exactly (both
`sha256sum` checks below), so the preimages are intact and trustworthy, and the diff against each
preimage is a minimal, single-purpose change matching this step's own spec verbatim — not a
distractor or partial/broken edit. No stepT6 report, transcript, or post-edit live session existed
yet, so Part D had not run. This step verifies that prior state independently (Part A, from this
step's own read of `state.db`, not from the comment's say-so), confirms C1/C2 are correct and
complete, and then executes Part D itself.

```
$ sha256sum -c against PREIMAGE.sha256 (both lines): OK, byte-for-byte identical to the
  .PREIMAGE copies. No further edit made to these two files in this step.
```

---

## PREDICTION (written before Part A)

The dominant cause is instruction-driven (SOUL's read-sources rule with nothing marking the cards
as already read), amplified by reachable-but-unscoped tools (`session_search`, the MCP protocol
utilities) and prior test sessions sitting in searchable history. Not model whim.

---

## PART A — why one turn became eleven

Reconstructed directly from `state.db` `messages` for session `20260910_155322_c8eda5`, in order
(zero model calls; a real read of an existing record):

| # | assistant action | reasoning shown | tool result (gist) |
|---|---|---|---|
| 1 | `tool_describe(["mcp__brain__open_note"])` | *(none captured)* | schema for open_note |
| 2 | `tool_call(mcp__brain__open_note, pointer=sources/intake/records/d9cb4668….md)` | — | full **raw original** record (131,708 B), truncated to a cache spillover file |
| 3 | `tool_search(["read local file contents"], limit=5)` | "Evaluating file reading options" | 12 reachable tools listed, incl. `session_search`, `mcp__brain__read_resource`, `open_call`, `open_note`, `search_history` |
| 4 | `tool_describe(["mcp__brain__search_history"])` | "Utilizing mcp search_history for MLS" | schema |
| 5 | 3× parallel `tool_call(mcp__brain__search_history, …)` (Fred/MLS/GVR/SnapStats/board terms) | — | 3 FTS result sets |
| 6 | `tool_describe(["mcp__brain__read_resource"])` | "Exploring Python file reading options" | schema |
| 7 | 3× parallel `tool_call(mcp__brain__search_history, …)` — quote-hunting: `"like, I think 11 boards"`, `"Fraser Valley" "Surrey" "Langley"`, `"GVR" "Fraser Valley" "boards"` | "Planning search for exact city names" | 3 more FTS result sets |
| 8 | `tool_call(mcp__brain__read_resource, uri=file:///home/liam/.hermes/profiles/david/cache/spillover/call_ns5qg…txt)` | "Planning resource access via file URI" | re-reads its **own truncated tool result** from call #2 via a raw file:// URI, to recover the full quote that got spilled out of context |
| 9 | `tool_describe(["session_search"])` | — | schema |
| 10 | `tool_call(session_search, query="\"like, I think 11 boards\" \"Fraser Valley\" cities Fred MLS", sort=newest, limit=3)` | — | surfaces **prior session `20260909_175150_486fe1`, titled "Find Fred Haiderzada GVR board details"** |
| 11 | final assistant answer | — | — |

**A1 — was the pre-model context already sufficient, and did T5 score the right thing?**
David's *first* action (before any visible reasoning text) was to `open_note` the **raw original
record**, not to answer from the already-assembled card. Diffing the actual card text (not
`claims.yaml`, which T5 wrongly used) against T5's 3 scoring facts:
- Fact 1 (MLS branded daily emails / notification visibility) — **not present** in the card at
  all; the card's bullets are ellipsis-truncated ("…") exactly where this level of detail would
  be, e.g. "Fred Haiderzada — said a real-estate project management workflow with transaction
  checkpo…".
- Fact 2 (GVR data-access follow-up) — present only as an **open question** ("What MLS or GVR
  data access will be available?"), not as a completed commitment the way T5 phrased it.
- Fact 3 (weekly buyer-facing market report wishlist) — **not present**; the closest surviving
  text is a truncated "Promotion candidates" bullet about a workflow/document tracker, unrelated
  to a buyer-facing report.
**Finding: T5's answer-scoring tested facts from `claims.yaml` (the full extraction), not from
what the assembled card actually contained.** That is a real, separate card-completeness defect
(the ellipsis truncation cuts off exactly the specific details a "what did he say about X"
question needs) — named here, not fixed, per Part B's gate (see below). It is not, by itself,
why the turn became 11 calls: even a complete card would not have stopped step 1 above, which
happened before any fact-gap could have been identified.

**A2 — the instruction actually driving the behaviour.** `/home/liam/.hermes/profiles/david/SOUL.md:114`:
> Read relevant canonical Brain sources before making claims that depend on organisational history.
Nothing in SOUL.md, `rules/`, or the (pre-fix) assembler preamble ever told David that the
"scoped canonical Brain notes" block **is** that pre-read set. The card body's own "Original:"
link (`[[sources/intake/records/d9cb4668….md|source]]`) points straight at the raw record — an
open invitation to open it, which is exactly what step 1 did.

**A3 — test-residue contamination, confirmed.** `session_search` call #10 above surfaced session
`20260909_175150_486fe1`, titled **"Find Fred Haiderzada GVR board details"**, run 2026-09-09 —
manual forensic-audit research from a prior day, sitting in searchable Hermes session history.
This is exactly the source of the answer's oddly-specific quotes ("11 boards", "Fraser
Valley"/"Obisford"/Surrey/Langley) and plausibly the "~CA$40/month" figure that does not match
either card or `claims.yaml`. **Named: test-residue contamination** — prior investigative
sessions are reachable and indistinguishable from real conversational continuity via
`session_search`.

**A4 — visible vs. reachable, mechanically established (zero model calls).**
- **Visible** (native KEEP toolset, per `hermes prompt-size --json`): 5 —
  `{clarify, memory, tool_call, tool_describe, tool_search}` (unchanged from T3/T4).
- **Reachable** under `tool_search`'s "auto" discovery, confirmed by direct
  `tools.mcp_tool_discovery.discover_mcp_tools()` call against David's live `HERMES_HOME`
  (same zero-model method T3 used): the `brain` MCP server exposed **10** tools pre-fix — 6
  domain tools (`open_note`, `search_history`, `open_call`, `search_calls`,
  `remember_brain_knowledge`, `brain_memory_status`) **plus 4 generic MCP-protocol bridge tools**
  every `MCPServer` exposes regardless of what the script defines (`get_prompt`, `list_prompts`,
  `list_resources`, `read_resource`) — this is T3's own Part 2 finding, re-confirmed live in T5's
  trace. Additionally, the native `session_search` toolset (`toolsets.py:126`,
  `"session_search": _ts(..., ["session_search"])`) is reachable whenever not explicitly
  disabled — it was not disabled at the time of T5's call. **This is an instrument finding
  against T3/T4: "five tools" measured only the visible array; the reachable array (14 tools:
  6 domain + 4 protocol + session_search + 3 more not exercised in this trace but present in the
  12-tool catalog T5's own `tool_search` call reported) was never measured or scoped.**

**A5 — provider-request ceiling.** `hermes_cli/_parser.py:250` (Hermes v0.21.1 source):
`--max-turns N` — "Maximum tool-calling iterations per conversation turn (default: 500, or
`agent.max_turns` in config)". This is a **per-invocation CLI flag**, resolved independently of
`config.yaml`'s `agent.max_turns: 150` and leaving the live profile config untouched — exactly
the mechanism needed for Part D's hard-stop-after-turn-1 detector.

---

## PART B — decision gate

Both named conditions hold:
- **(i)** SOUL.md:114 directs source reads before claims depending on organisational history, and
  (pre-fix) nothing marked the pre-fetched cards as already satisfying it.
- **(ii)** Reachable tools with no documented David path: `session_search` (SOUL.md only
  documents native *memory* for conversational continuity, at SOUL.md:107 — a different
  mechanism; `rules/david_thread_contract.md` documents the assembler's own conversation block,
  not the `session_search` tool) and the 4 generic MCP protocol-bridge tools (raw, unscoped
  `resources`/`prompts` access — T5's trace shows `read_resource` used with an arbitrary
  `file://` URI to read a local cache file, which is a materially different, wider surface than
  the domain-scoped `open_note`).

A3's card-completeness gap (A1) is real but secondary: it explains why the answer was imperfect,
not why the call count reached 11 — step 1 (immediately opening the raw record) preceded any
possible fact-gap discovery. **Proceeding to Part C.**

---

## PART C — repair (David only)

### C1 — reachable-scope leak (mechanical)

**Exact change** (already present on disk at step start; preimage verified intact, sha256
matches `PREIMAGE.sha256`; not re-applied, no further edit made):
- `/home/liam/.hermes/profiles/david/config.yaml`: `agent.disabled_toolsets` gained
  `- session_search`; `mcp_servers.brain` gained `tools: {resources: false, prompts: false}`.
- **Rollback:** `/home/liam/ttros_backups/stepT6_2026-09-10/david_config.yaml.PREIMAGE` (restore
  by copy; flag-flip equivalent: remove the two added keys).

`session_search` has no documented David path (checked SOUL.md and `rules/*.md` in this step,
A2/A4 above) — disabled outright, not kept.

**Proof, this step, zero model calls**, via `tools.mcp_tool_discovery.discover_mcp_tools()`
against David's live `HERMES_HOME` post-fix:
- Reachable brain-MCP set is now exactly the 6 domain tools:
  `{open_note, search_history, open_call, search_calls, remember_brain_knowledge,
  brain_memory_status}` — **ASSERT PRESENT: PASS**.
- The 4 protocol utilities (`read_resource`, `get_prompt`, `list_prompts`, `list_resources`) are
  gone — **ASSERT ABSENT: PASS**.
- Rehearsed both directions: falsely claiming `open_note` absent is correctly caught as wrong
  (tool is actually present); falsely claiming `nonexistent_tool_xyz` present is correctly caught
  as wrong. The checker can return both answers.
- Visible set unchanged: `hermes -p david prompt-size --json` → `tools.count == 5`, same 5 names
  as T3/T4/T5.

`session_search`'s removal from the native toolset registry is not independently re-verified by a
second zero-model instrument in this step (no equivalent bare-function call was found in the time
available); its absence is inferred from `toolsets.py`'s registration contract
(`disabled_toolsets` membership removing a named toolset wholesale, the same mechanism T3 already
proved for `browser`/`web`/etc.) and will be confirmed empirically by D1's live result showing no
`session_search` call.

### C2 — instruction precedence (behavioural)

**Exact change** (already present on disk at step start; preimage verified intact; not
re-applied): `tools/context_assembler.py`, `_scoped_note_block()`, one sentence appended to the
block's own preamble (comment tagged `F-TOOLOVERREACH-1 (Step T6, 2026-09-10)`):
> Selected N canonical note(s); source discovery used zero model tokens. **These are the pre-read
> Brain sources for this request — answer from them; call a brain tool only for a named fact they
> do not contain, with one targeted read, not a history search.**
- **Rollback:** `/home/liam/ttros_backups/stepT6_2026-09-10/context_assembler.py.PREIMAGE`
  (restore by copy).

Placed at the assembler's block preamble (not SOUL.md), because A2 shows the operative gap is
"nothing marks this block as the pre-read source" — a fact about *this specific block's own
framing*, not a general SOUL rule change; only one of the two named locations was touched, per
instruction.

**Proof, this step:** re-ran T1's six `assemble()` cases against the current (already-patched)
assembler:

| Case | before (T1/T3/T4/T5) | now | delta |
|---|---:|---:|---:|
| Fred/MLS | 4,966 B | 5,148 B | **+182 B** |
| CCI | 7,262 B | 7,444 B | **+182 B** |
| Andrea | 4,651 B | 4,833 B | **+182 B** |
| Negative control 1 | 192 B | 192 B | 0 |
| Negative control 2 | 192 B | 192 B | 0 |
| Fallback control | 192 B | 192 B | 0 |

The appended sentence is exactly 182 UTF-8 bytes (`len(sentence.encode('utf-8'))`, checked
directly) — the delta on every reads-present case equals exactly the wording change, nothing
else moved. Full suite, run now in this step: **829 passed, 0 failed** (same population as T5's
precondition run).

---

## PART D — live proof, two turns

Instrument: `scripts/stepT6_live_overretrieval_repair.py`. Counts CLI invocations (max 2, hard
stop, no retry). A5 found a genuine per-invocation cap (`--max-turns`, independent of the live
profile's `agent.max_turns: 150`): **set to 6** for both turns. `--usage-file` gives `api_calls`
per invocation; the instrument hard-stops before turn 2 if turn 1's `api_calls > 6` (does not run
turn 2 in that case).

### D1 — Fred/MLS, verbatim as T5

**Facts the answer must contain** (drawn only from the actual card text quoted in Part A1 above,
not `claims.yaml`):
1. Fred forwarded the SnapStats sheet during the meeting.
2. An open question remained about what MLS or GVR data access would be available.
3. Fred preferred exploring a project-management-style transaction/workflow dashboard.
4. The idea that a SnapStats-style dashboard could potentially be built and sold to other
   realtors was floated.

**Forbidden claims:** the specific GVR board count/number, or the Fraser Valley/Surrey/Langley
city names/quote (confirmed absent from the assembled context by direct offline check this step:
`"11 boards"`, `"fraser"`, `"surrey"`, `"langley"` all absent from the card text; only unrelated
"dashboard" substrings match "board"); no CCI/Andrea Roberts content.

**Predicted:** `api_calls` ≤ 2 (target 1); 0 tool calls; if any, at most one targeted brain read,
no `session_search`, no `search_history`, no protocol-utility call.

### D2 — over-suppression control

Question: "In my meeting with Fred, what were his exact words about how many GVR boards there
are?" Offline-confirmed this step (see above) that the card does not contain this — a genuine
gap, not a suppressed-but-present fact. **Predicted:** David makes a targeted brain read (most
plausibly `open_note` on the raw record, or `search_history`) and returns the "I think 11 boards"
quote correctly, within `api_calls` ≤ 4. A refusal or memory-only answer here would mean C1/C2
over-suppressed.

---

## Part D — what actually happened

Before running `scripts/stepT6_live_overretrieval_repair.py`, it refused to run: its transcript
file already existed. Investigating rather than overwriting: this step's own two-live-turn
budget had **already been spent** — `scripts/stepT6_live_overretrieval_repair.txt` (timestamp
16:44) contained a complete D1 + D2 run, with real, verified session records in `state.db`
(session ids `20260910_164259_695793` and `20260910_164318_637846`, both `cwd =
/home/liam/agentic-os-live`, `api_call_count`/`tool_call_count` matching the transcript exactly).
**No live call was made by this pass of the step.** Per the step's own "at most two live
CLI-David turns" authorization (a budget for the step, not per attempt) and "do not rerun, do not
add a third turn," these two already-consumed turns are treated as Part D's real result.

One material honesty note: D1's actual question matched this step's own pre-registered
prediction exactly (verbatim Fred/MLS question). D2's actual question — "what is the exact name
of the MLS platform Fred said he uses to see when his last notification went out and when a
client last opened the collaboration center?" — differs from the GVR-board-count question
predicted above. D2's fact was independently confirmed absent from the assembled context in this
pass (`"paragon"`, `"collaboration center"`, `"notification"` all absent from the card block,
checked directly), so the over-suppression-control premise still holds; it is scored against the
step's fixed generic bar (targeted read succeeds, `api_calls` ≤ 4, no refusal), not against the
specific pre-written facts drafted for a different question.

### D1 result

`api_calls: 1`, `tool_call_count: 0`, `cache_read_tokens: 0` (fresh session, no tool call at all).
Answer covers: SnapStats sheet forwarded ✓; waiting on GVR for data access ✓; preferred
project-management workflow dashboard over a simpler tracker ✓; general dashboard-product framing
✓ (facts 1–4 all present). **But the answer also states:** "He gave a number for boards under
GVR: 'like, I think 11 boards.'" — a forbidden claim, present despite zero tool calls.

**Traced to source, this step, zero model calls:** the manifest for this exact session
(`queue/context_assemblies/hermes-20260910_164259_695793-….json`) shows the "relevant session
recency" block (2,818 B, a normal, always-included part of the deterministic assembly, unrelated
to `_scoped_note_block`) containing a fragment referencing "...a specific number of realty boards
under GVR and names specific [cities]... covered by the Fraser Valley board. What number does he
give..." — this is a fragment of **T5's own prior turn**, pulled in because the assembler's
session-recency selection treats recent same-topic sessions as relevant context, independent of
`tool_search`/MCP reachability entirely. **This is a second, distinct contamination channel from
A3's `session_search` finding** — a deterministic, pre-model one that C1 (toolset/MCP scoping) and
C2 (the block preamble wording) do not touch, because it lives in a different context block. D1
**FAILS** the "no forbidden claim" criterion for this reason, despite passing every call-count
and tool-name criterion (`api_calls ≤ 2`: yes; no `session_search`/`search_history`/protocol
calls: yes, there were no tool calls at all; every in-context fact present: yes).

### D2 result

`api_calls: 9`, `tool_call_count: 12` — `tool_describe` ×1, `mcp__brain__open_note` ×2,
`mcp__brain__search_history` ×9. **Zero** `session_search` calls, **zero** protocol-utility calls
(`read_resource`/`get_prompt`/`list_prompts`/`list_resources`) — C1's reachable-scope fix held
completely; every tool call was to a documented, kept domain tool. The answer ("Fred said he uses
Paragon — specifically the MLS Paragon system... Collaboration Center") is **correct**, verified
against the raw record (`sources/intake/records/d9cb4668….md:102`, "on MLS paragon, I can see when
was the last notification went to them? And when was the last time they opened the collaboration
center..."). So retrieval succeeded and did not over-suppress. But **D2 FAILS** the `api_calls ≤ 4`
ceiling (actual 9): 9 `search_history` calls is a history-search spree, not "one targeted read" —
C2's wording redirected David away from `session_search`/protocol tools entirely (a real, complete
win) but did not constrain *how many* legitimate domain-tool calls it makes while chasing one
missing fact.

## Verdict

**FAIL**, named causes for each:
- **D1 fails** on "no forbidden claim," caused by the assembler's "relevant session recency"
  block surfacing T5's own prior session content — a contamination channel neither C1 nor C2
  addresses (both target tool reachability and instruction framing, not cross-session recency
  selection). Everything else about D1 passed, including a genuine, large, real improvement:
  `api_calls` 11 → 1, `tool_call_count` 14 → 0 for the *identical* verbatim question.
- **D2 fails** on the `api_calls ≤ 4` ceiling (actual 9), caused by tool behaviour: C1+C2
  successfully confined David to documented, in-scope brain tools (a complete, confirmed win —
  no reachable-scope leak at all), but did not cap repeated legitimate calls once it started
  searching for a genuinely-missing fact.

C1 and C2 are real, verified, working repairs for exactly what they target (reachable-scope
leakage and instruction framing) — proven both offline (Part C) and live (D1's tool-call count,
D2's tool-name list). They do not fully close the over-retrieval problem: a separate,
un-repaired context-assembly channel (session recency) and an unconstrained call-count on
legitimate-tool use both remain. Per the step's own rule, this is reported, not fixed further,
and no third turn is added.

