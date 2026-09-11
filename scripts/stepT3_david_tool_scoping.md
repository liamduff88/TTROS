# STEP T3 — Scope David's profile tool exposure, one lever at a time. ZERO model calls.

Surface: CLI-David (`hermes -p david`), config-only. No David/Hermes/provider call was made
anywhere in this task. Every number is either a real, live, zero-model-call offline measurement
(`hermes prompt-size --json` — Hermes's own official offline diagnostic, "matches what ships on
the wire," no network call; direct calls to `tools.mcp_tool_discovery.discover_mcp_tools` /
`tools.registry.get_definitions` / `tools.context_assembler.assemble()`) or a real file listing
(`ls`, `wc -c`, `cat`) or a real, native, zero-model CLI subcommand (`hermes memory reset`).

---

## PART 0 — THE 29 NATIVE TOOLS: KEEP/REMOVE, grounded in David's documented paths

**Method:** SOUL.md, `rules/david_execution_handoff.md` (the conversation-vs-execution contract),
`rules/david_thread_contract.md`, the action-boundaries block
(`tools/context_assembler.py:_action_boundaries`), and every TTROS code path shown in STEP T2 Part 0
to reach David. Not derived from the 21-question A–E4 pass (that pass never exercised
queue/runner/worker/connector paths).

| Tool | Bytes | KEEP/REMOVE | Reason (documented path or its absence) |
|---|---:|---|---|
| `memory` | 3,299 | **KEEP** | SOUL.md, "Memory": *"Use native David memory for conversational continuity, Liam's preferences, ongoing interpretations, hypotheses, and unresolved discussion context."* Direct, explicit, documented. |
| `clarify` | 1,639 | **KEEP** | `david_execution_handoff.md` state 3 ("Materially ambiguous... Ask exactly one clarifying question and stop") + SOUL.md ("Ask one question at a time..."). The 21-question pass ran non-interactively (`-z`), which cannot exercise this — but the dashboard `ask-david` endpoint and Telegram bridge (T2 Part 0 rows 2–3) are real, live, interactive David surfaces where a clarifying question is a documented, expected behavior. |
| `tool_search` | 2,492 | **KEEP** | Bridge tool for MCP tools (`mcp__brain__*`). Necessary as long as Part 2 leaves `tools.tool_search.enabled` at `"auto"` — see Part 2. |
| `tool_call` | 525 | **KEEP** | Same bridge triad; invokes the deferred `mcp__brain__*` tools David's SOUL.md and STEP U's own Phase-5 classification name as TTROS-specific and load-bearing (search_calls/search_history/open_call/open_note — "Read relevant canonical Brain sources before making claims that depend on organisational history"). |
| `tool_describe` | 499 | **KEEP** | Same bridge triad — loads the schema `tool_call` needs. |
| `delegate_task` | 4,414 | **REMOVE** | `david_execution_handoff.md`: *"David decides whether a message is conversation or work. Orchestration Hermes owns everything after that decision — decomposition ... workers ... Emitting an `execution_handoff` is not creating queue work. It is not delegating."* David's own execution mechanism is a structured JSON text block in his reply, never the native `delegate_task` tool. No documented path calls for it. |
| `terminal` | 3,374 | **REMOVE** | Same contract: David never executes; `aos-orchestrator` (a separate, already-restricted profile) is the execution profile (T2 Part 0 row 5/7/10/11). No documented path has David running shell commands. |
| `execute_code` | 3,012 | **REMOVE** | Same reasoning as `terminal` — programmatic tool-calling-with-logic belongs to the execution profile, not the conversational/handoff-emitting profile. |
| `write_file` | 898 | **REMOVE** | Action boundaries: *"Gmail remains draft-only"* — the only documented drafting path is Gmail-draft, not local file writes. No documented path. |
| `patch` | 1,640 | **REMOVE** | Same — no documented path; file editing is execution-profile work. |
| `search_files` | 2,332 | **REMOVE** | No documented path — repo-wide search is execution-profile / operator work, not conversational-David work. |
| `read_file` | 1,169 | **REMOVE** | Explicit judgement (see below). |
| `skill_view` | 932 | **REMOVE** | See Lever B judgement below. |
| `skill_manage` | 2,390 | **REMOVE** | Same. |
| `skills_list` | 308 | **REMOVE** | Same. |
| `browser_vision` | 1,197 | **REMOVE** | No documented path mentions browsing anywhere in SOUL.md, the handoff contract, or action boundaries. |
| `browser_console` | 1,012 | **REMOVE** | Same. |
| `browser_snapshot` | 966 | **REMOVE** | Same. |
| `browser_navigate` | 945 | **REMOVE** | Same. |
| `browser_type` | 507 | **REMOVE** | Same. |
| `browser_click` | 468 | **REMOVE** | Same. |
| `browser_scroll` | 412 | **REMOVE** | Same. |
| `browser_press` | 401 | **REMOVE** | Same. |
| `browser_get_images` | 317 | **REMOVE** | Same. |
| `browser_back` | 232 | **REMOVE** | Same. |
| `web_search` | 797 | **REMOVE** | No documented path — the documented knowledge path is the TTROS Business Brain vault ("Read relevant canonical Brain sources..."), not live web search. |
| `web_extract` | 1,119 | **REMOVE** | Same. |
| `vision_analyze` | 848 | **REMOVE** | No documented path — no image-analysis mention anywhere. |
| `text_to_speech` | 1,886 | **REMOVE** | No documented path — David's surfaces (dashboard, Telegram, CLI) are text. |

**Totals:** KEEP = 5 tools / 8,454 B. REMOVE = 24 tools / 31,634 B (40,088 − 8,454, reconciling
exactly to the +58 B array-overhead figure T2 already established).

### The five specific judgements, answered explicitly

- **`memory`** — **KEEP.** SOUL.md directly and explicitly assigns native memory a job
  (conversational continuity, preferences, hypotheses). Removing the tool would remove David's
  only way to write to it. Zero calls in the 21-question pass is explained by that pass's own
  scope (non-interactive knowledge questions, no multi-turn continuity to build) — it is not
  evidence the documented path is unused.
- **`clarify`** — **KEEP.** The non-interactive `-z` pass structurally cannot exercise it. The
  handoff contract's own state 3 ("Materially ambiguous... ask exactly one clarifying question")
  is a documented behavior that live, interactive surfaces (dashboard ask-david, Telegram) can and
  do trigger.
- **`read_file`** — **REMOVE**, not kept via a custom toolset. The one real call in the pass has no
  grounded documented need: Repair 1's own diagnosis (T1) established that the content David might
  try to "read" (TTROS workflow/skill files, Brain notes) is *already inlined in full* in the
  assembled context — the same class of misfire as the `skill_view` failures, just aimed at a
  different tool. Building a single-tool custom toolset for a tool with zero grounded use case adds
  complexity without a documented justification; it is removed with its three `file`-toolset
  siblings (Lever A) instead.
- **`terminal`, `execute_code`, `delegate_task`, `write_file`, `patch`** — **REMOVE**, confirmed
  from the contract text itself, not the name: `rules/david_execution_handoff.md` states plainly
  that David decides conversation-vs-work and *"Orchestration Hermes owns everything after that
  decision,"* and that emitting the JSON handoff *"is not delegating... is not execution of any
  kind."* `write_file`/`patch` have no separate grounding either (Gmail-draft-only is the one
  documented drafting path, and it is not a local-file mechanism).
- **`tool_search`, `tool_call`, `tool_describe`** — **KEEP**, decided only after Part 2 (below)
  confirmed `tools.tool_search.enabled` stays `"auto"`, which requires this bridge triad for the
  brain MCP tools to remain reachable at all.

---

## PART 1 — CLEAR THE TEST RESIDUE

**Mechanism used:** the supported native CLI subcommand, not a hand-edit —
`hermes -p david memory reset --target memory --yes`. Confirmed via reading
`hermes_cli/main_agent_cmds.py::_cmd_memory_reset`: it targets exactly
`<HERMES_HOME>/memories/MEMORY.md` (deleting the file outright when `--target memory`), makes no
model call, and is scoped by `HERMES_HOME`/`-p` resolution the same way every other Hermes
invocation is.

**Before:** `~/.hermes/profiles/david/memories/MEMORY.md` = **46 bytes**, entire content
`"User asked David to remember the word: banana."` — confirmed by direct file read; there was
nothing else in it and no `USER.md` existed alongside it, so `--target memory` (not `--target all`)
is precisely scoped to the one file that needed clearing.

**Command run:**
```
/home/liam/.local/bin/hermes -p david memory reset --target memory --yes
```
Output: `✓ Deleted MEMORY.md (agent notes)`.

**After:** file no longer exists (0 bytes). Confirmed independently via
`hermes -p david prompt-size --json` → `"memory": {"chars": 0, "bytes": 0}` in every subsequent
measurement this task took.

---

## PART 2 — THE EAGER MCP ARRAY, MEASURED BEFORE TOUCHING THE BRIDGE

**Method:** called `tools.mcp_tool_discovery.discover_mcp_tools()` directly (the same function
Hermes itself calls, and the same one `operator_lean_oneshot.py::require_operator_tools` uses for
its own fail-closed check) against David's live `HERMES_HOME`, then
`tools.registry.get_definitions()` for full JSON schemas. This spawns David's own two configured
MCP server subprocesses locally (no model call, no dispatch) — the same class of local action
`operator_lean_oneshot.py --inspect-preamble` already performs safely in this repo.

**Result — a real, capable-of-failing measurement, not an assumption:**

| Server | Result | Tools | Bytes |
|---|---|---:|---:|
| `brain` | **CONNECTED** | 10: `search_calls`, `search_history`, `open_call`, `open_note`, `remember_brain_knowledge`, `brain_memory_status` (the 6 TTROS-specific tools STEP U's Phase 5 already classified as keep-worthy) **plus** 4 generic MCP-protocol bridge tools every `MCPServer` exposes regardless of what the script defines (`get_prompt`, `list_prompts`, `list_resources`, `read_resource`) | 4,506 |
| `queue` | **FAILED** — `MCPError: Connection closed` after 3 retries | 0 | 0 |
| **Total eager array** | | **10** | **4,526 B / 1,400 TTROS-estimated tokens** (array overhead +20 B) |

**Why `queue` fails:** `tools/queue_mcp.py` does not exist on disk (already deleted in the dirty
tree before this session, per STEP U's own finding — not this task's doing, not touched). David's
`config.yaml` still registers it; the server simply never starts, contributing 0 tools whether
`tool_search` is `"auto"` or `"off"`. This is unrelated to the lever decision below and is not
fixed here (outside this task's "config only, one lever at a time" scope, and fixing a missing
script is not a toolset-scoping decision).

**The real number is larger than T2's speculative estimate** (T2 guessed ≈2,432 B from 4 tools ×
608 B, using the *compact* `tool_describe`-result format as a stand-in). The actual **eager, full
JSON-schema** cost is 4,526 B for 10 tools (the 4 generic protocol tools were not anticipated) —
nearly double the earlier guess.

**The arithmetic, run explicitly:**

- **Fixed cost of `"off"` (eager):** +4,526 B / +1,400 TTROS-estimated tokens added to the `tools`
  array on **every single request**, forever, including the real, provider-exact zero-tool-call
  anchor T1 used (A2: `api_calls=1`, `cache_read_tokens=0`, 23,330 real tokens) — a permanent ~6%
  tax on that baseline alone, and a permanent tax on every trivial/direct-answer question that
  never needed a brain tool at all.
- **Benefit removed:** `tool_describe` round trips, at T1's own measured ~28,884 tokens per round
  trip (a full extra provider request, not just the small result payload). Pre-Repair-2 upper
  bound: 14 calls across the 21-question pass. **Post-Repair-2 (the number this task actually
  needs) is unmeasurable without a live model call, which this task makes none of** — and Repair 2
  was purpose-built to intercept exactly the `search_calls`/`search_history`/`open_note` pattern
  that drove most of that pre-repair traffic, so the honest expectation (T1's own words) is that it
  has "sharply shrunk," not held at 14.
- **Break-even, worked through explicitly:** over that same 21-question pass, the fixed eager tax
  alone would cost 21 × 1,400 ≈ **29,400 tokens**, unconditionally, on every question including the
  ones needing zero brain-tool interaction — already close to the *entire pre-repair* upper-bound
  benefit (14 round trips × 28,884 ≈ 404,376 tokens **only if none of Repair 2's reduction is
  real**; if Repair 2 cut real traffic to even 1–2 residual calls, as its own design intends, the
  fixed tax exceeds the remaining benefit). And the fixed tax does not stop after 21 questions — it
  recurs on every request forever, while the benefit keeps shrinking as Repair 2 (and its
  descendants) intercept more of the pattern that used to require it.
  **[See CORRECTION 2026-09-10 at the end of this file — this arithmetic was wrong at N=2, and the
  4,526 B was priced gross, not net of the bridge triad it replaces.]**

**Decision: NO CHANGE — leave `tools.tool_search.enabled` at the inherited `"auto"` default for
David.** The eager array is larger than previously estimated, the tax is unconditional and
permanent, and the benefit is already-shrinking and unmeasurable without a model call this task is
forbidden from making. This is a complete "no" result, not a placeholder — Lever D is not applied.

---

## PART 3 — APPLY, ONE LEVER AT A TIME (david's profile only)

**Instrument:** `hermes -p david prompt-size --json` — Hermes's own official offline diagnostic.
Docstring: *"Builds a real inspection agent (so the numbers match what ships on the wire), but
never makes a network call."* Baseline taken **after** Part 1's memory reset (so `memory` already
reads 0 B in every measurement below — real, not zeroed-out separately).

**Baseline (before any lever):** tools 39,147 B / 29 tools; system_prompt 32,191 B (of which
skills_index = 8,656 B, matching T2's own captured-request figure for the native skills catalog
exactly).

*(Named instrument-boundary caveat, disclosed not swept under: `prompt-size`'s `system_prompt`
includes a third tier — `"context (AGENTS.md/cwd files)"`, 3,753–3,773 B, constant across every
measurement in this task — that T1/T2's real captured-request `instructions` decomposition
[27,384 B, itemized to 8 named segments] did not include. It does not affect any lever's
*delta* below, since it is unchanged by every lever; it only affects the *absolute* comparison to
94,102 B / 110,886 B, flagged explicitly in Acceptance §4.)*

### Lever A — the clearly-unused surfaces (browser, web, vision, tts, file)

**Exact change** to `~/.hermes/profiles/david/config.yaml`:
```yaml
agent:
  max_turns: 150
  disabled_toolsets:
    - browser
    - web
    - vision
    - tts
    - file
```
**Exact rollback:** delete the `disabled_toolsets:` key and its 5 list lines, restoring `agent:`
to just `max_turns: 150`.

**Result:** tools 39,147 → **20,957 B** (Δ **−18,190 B**, 29 → 11 tools — exactly the 18 tools in
`browser`(10) + `web`(2) + `vision`(1) + `tts`(1) + `file`(4)). system_prompt 32,191 → **32,104 B**
(Δ **−87 B** — a small, real, explainable shrink: the skills-index's own "prefer web_search or
terminal" hint text drops the "web_search or " clause once `web_search` is gone). skills_index
unchanged (8,656 B, as expected — Lever A doesn't touch the `skills` toolset). Delta from baseline
combined (tools+system_prompt): **−18,277 B**.

### Lever B — the skills toolset

**Exact change:** add `- skills` to the `disabled_toolsets` list (now 6 entries).
**Exact rollback:** remove that one line.

**Result:** tools 20,957 → **17,330 B** (Δ **−3,627 B**, 11 → 8 tools — `skill_view`+`skill_manage`+
`skills_list`, matching T2's own 3,630 B group total to within 3 B of instrument rounding).
system_prompt 32,104 → **21,725 B** (Δ **−10,379 B**). **skills_index measured (not assumed): 0
bytes** — confirmed both via `prompt-size`'s own extraction and, separately, by grepping the fully
constructed system-prompt text directly: `"<available_skills>" in full` → **False**, `"skill_view"
in full` → **False**, `"## Skills" in full` → **False**. This satisfies Acceptance §3.

**Lever B supersedes T1's Repair 1, and the wording should be LEFT IN PLACE, not reverted:**
T1's Repair 1 added one disambiguating sentence to `_matching_workflows_block`'s preamble telling
David not to call `skill_view`/`skill_manage`/`tool_search` on the block's own `id=` projections.
With Lever B applied, `skill_view`/`skill_manage`/`skills_list` no longer exist in David's tool set
at all — that specific misfire is now **structurally impossible**, not merely discouraged, which is
strictly stronger than a prompt-wording fix. Left in place anyway, for three reasons: (1) the
sentence remains literally true regardless of tool availability (the content genuinely is already
inlined in full); (2) `tool_search` is still named in that sentence and is still a live, present
tool (Part 2's decision keeps it) — the sentence still guards against David trying to `tool_search`
the `id=` value, a route Lever B does not close; (3) reverting it is an edit to
`context_assembler.py`, which is out of this task's scope beyond this explicit decision, and
leaving a still-true, still-partially-load-bearing, already-priced-in (362 B) sentence in place is
the lower-risk option. **Recommendation: leave as-is.**

### Lever C — the execution group (grounded in the handoff contract, Part 0)

**Exact change:** add `- terminal`, `- code_execution`, `- delegation` to `disabled_toolsets`
(now 9 entries).
**Exact rollback:** remove those three lines.

**Result:** tools 17,330 → **7,493 B** (Δ **−9,837 B**, 8 → 5 tools). system_prompt unchanged
(21,725 B — the execution group has no skills-catalog or prompt-text side effect). **This delta is
smaller than the naive Part-0 group total (delegate_task 4,414 + terminal 3,374 + execute_code
3,012 = 10,800 B) by 963 B, for a real, inspectable, non-arbitrary reason, not instrument
noise:** `execute_code`'s own schema is dynamically rewritten
(`model_tools.py::_rewrite_execute_code`, *"List only sandbox tools that are actually
available"*) to enumerate only the sandbox tools still present — since Lever A already removed
`web_search`/browser tools before Lever C ran, `execute_code`'s own schema had already shrunk from
its original 3,012 B to 1,947 B by the time Lever C measured it. Confirmed directly from the
per-toolset breakdown (`code_execution`: 1,947 B at the Lever-B snapshot, not 3,012 B) — the
group-sum arithmetic in Part 0 is a *ceiling* computed from the unmodified 29-tool baseline, and
real, order-dependent dynamic rewriters make the *realized* saving from any later lever slightly
smaller. Named, not hidden.

### Lever D — `tools.tool_search.enabled`

**Not applied.** Part 2's arithmetic does not support it (see above). `"auto"` stays, inherited,
untouched, exactly as it was before this task.

### Cumulative, all three applied levers

| | tools bytes | system_prompt bytes | tools count |
|---|---:|---:|---:|
| Baseline (post-Part-1) | 39,147 | 32,191 | 29 |
| + Lever A | 20,957 | 32,104 | 11 |
| + Lever B | 17,330 | 21,725 | 8 |
| + Lever C | **7,493** | **21,725** | **5** |
| **Total delta** | **−31,654** | **−10,466** | **−24** |

(The 31,654 B tools delta matches Part 0's KEEP/REMOVE-table-derived 31,634 B ceiling to within
20 B of real dynamic-rewriter/serialization variance — reconciled, not coincidental.)

---

## ACCEPTANCE

### 1 — T1's six cases, re-run unchanged against `assemble()` directly (zero model calls)

All six hold **byte-identical** to T1/T2's own tables — no code in `context_assembler.py` was
touched by this task, so this is confirmation, not surprise:

| Case | Cards selected | Bytes |
|---|---|---:|
| Fred/MLS | `d9cb4668...card.md`, `kenneth-meeting-may-27.card.md` | 4,966 |
| CCI | `call-kenneth-after-first-cci`, `first-call-cci`, `cci-second-call-june-15` | 7,262 |
| Andrea (E5) | `andrea-roberts-june-26`, `andrea-second-call-june-30` | 4,651 |
| Negative control 1 | *(none)* | 192 |
| Negative control 2 (trivial) | *(none)* | 192 |
| Fallback control | *(none)* | 192 |

Both negative controls and the fallback correctly return no cards. No regression.

### 2 — Tool-array assertions, capable of failing both ways

Built the same offline inspection agent `hermes prompt-size` uses, against David's live
post-lever config. Resolved tool set: exactly `{clarify, memory, tool_call, tool_describe,
tool_search}` (5 tools).

- **ASSERT PRESENT** (5 KEEP tools): **PASS**.
- **ASSERT ABSENT** (24 REMOVE tools): **PASS**.
- **Rehearsed negative case, run to prove the checker can fail, not just print PASS:**
  deliberately asserted a nonexistent tool (`nonexistent_tool_xyz`) was present →
  **correctly reported FAIL**. This satisfies the "must be capable of returning both answers"
  requirement.

### 3 — Native `available_skills` catalog, measured absent

Confirmed three independent ways on the actual constructed payload (not assumed): `skills_index`
size = 0 B; `"<available_skills>"` not in the full system prompt; `"skill_view"` not in the full
system prompt. All three: **absent**.

### 4 — Final Fred request, all levers applied

| Component | Bytes |
|---|---:|
| Tools (5 schemas) | 7,493 |
| System prompt (instructions-equivalent, incl. the disclosed +3,773 B `AGENTS.md/cwd` tier) | 21,725 |
| Assembled context + question (`render()`, fresh this run) | 43,422 |
| **Total** | **72,640** |
| vs. T1's 110,886 B | **−38,246 B, −34.5%** |
| vs. the 94,102 B original baseline | **−21,462 B, −22.8%** |

**No invented savings, stated plainly:** this reduction is real and is the direct, arithmetic sum
of Part 3's measured lever deltas (tools −31,654 B; system_prompt −10,466 B) applied to numbers
that already include Repair 1/2's retrieval-side additions untouched. The one honest asterisk: the
94,102 B / 110,886 B baselines were computed from a real captured **request dump** whose
`instructions` decomposition (27,384 B) did not include the ~3,773 B `AGENTS.md/cwd files` tier
that `prompt-size` — a different, offline instrument — shows is actually part of the real
constructed system prompt. That tier is **constant** across every before/after measurement in this
task (it cannot be a lever effect), so it does not change *which* savings are real or *how much*
each lever moved — it only means the two absolute totals being compared here were built by two
different (both real, both zero-model-call) instruments, one of which apparently under-accounted
this tier. Named as a finding for whoever next reconciles the two instruments, not resolved here.

---

## PART 4 — THE LATENT FALLBACK: NO SINGLE BOUNDARY EXISTS

Checked whether one Python-level chokepoint could carry a one-line "fail loudly if no profile
resolved" assertion. It does not exist. TTROS's Hermes invocations fan out through at least three
independent shapes, confirmed by direct inspection:

1. **Ad hoc Python subprocess calls** in `scripts/*.py` (`step3_b7_harness.py`,
   `step5_b7_growth_harness.py`, `step6_b7_tools_harness.py`) and `tools/source_intake_semantic.py`
   — each defines its **own** local `HERMES_BIN` constant and its own `subprocess.run([...])` call;
   there is no shared Python helper module across them (confirmed by grep — only
   `step3_b7_harness.py` even defines `HERMES_BIN`, the others don't import it from anywhere).
2. **The shared shell coordinator**, `tools/aos-hermes-coordinator.sh` — used by every
   dashboard-backend-originated call via `_run_hermes_message` (`dashboard/backend/main.py:3927`).
   This one already has its own fail-loud guard: `profile` defaults to the named
   `"aos-orchestrator"` (never blank), it validates the profile against a whitelist
   (`case "$profile" in ...; *) echo "not an Agentic OS runtime profile"`), and it checks
   `profile_home` exists on disk before invoking `hermes -p "$profile"` — it can never reach the
   Hermes-internal bare-root fallback. No further assertion is needed here; it already fails
   loudly.
3. **Per-profile shell launchers**, e.g. `tools/aos-hermes-operator-lean.sh`, which export
   `HERMES_HOME` directly rather than passing `-p`.

None of these three shapes wraps the other two. Adding an assertion to any one of them protects
only that shape's future callers, and there is no fourth, lower-level place all three already pass
through. Per this task's own instruction, this is reported rather than solved by scattering a copy
of the same check into three unrelated files (which would itself be a small piece of new,
un-asked-for architecture). **No code was changed for Part 4.**

---

## REGRESSION

**Full suite** (`.venv/bin/python -m pytest -q`, run to completion this session, 377.31 s):
**828 passed, 1 failed, 223 subtests passed.** The 1 failure —
`test_hermes_context_plugin.py::HermesContextPluginTest::test_unregistered_profile_receives_no_context`
(`PermissionError: [Errno 13] Permission denied: hooks/context_assembler_hook.py`) — is the same
pre-existing file-permission gap T1 and T2 both named, on a file this task never touched.

**Population:** `pytest --collect-only -q` → **829 tests collected**, identical to T2's own figure
— no drift since T2 ran. This task's changes were entirely outside the repo (David's
`~/.hermes/profiles/david/config.yaml` and `.../memories/MEMORY.md`), so zero effect on repo test
collection was expected and confirmed.

**`git diff --check`:** exit 2, the same two pre-existing whitespace findings named by T1/T2
(`context/TOKEN_POLICY.md:94`, `hooks/token_budget_check.md:54`), both already present before this
session started and untouched by it. No new findings.

**Confirmed via `git status`/`git diff --stat`:** no repository file was modified by this task —
every edit landed in `~/.hermes/profiles/david/`, outside the repo, exactly per the "david's
profile only" hard boundary.

---

## CLOSEOUT

**Model calls: 0. David/Hermes/provider turns: 0.**

**Part 0:** 5 tools KEEP (`memory`, `clarify`, `tool_search`, `tool_call`, `tool_describe` —
8,454 B), 24 REMOVE (31,634 B). All five specific judgements answered explicitly above, each
grounded in SOUL.md / the execution handoff contract / action boundaries, or their documented
absence — not defaulted from the 21-question pass.

**Part 1:** MEMORY.md — before 46 B (`"User asked David to remember the word: banana."`), after
0 B (file deleted via the supported `hermes memory reset --target memory --yes` CLI path).

**Part 2:** eager MCP array = 4,526 B / 1,400 TTROS-estimated tokens for 10 tools (David's 6
TTROS-specific brain tools + 4 generic MCP-protocol tools neither T1 nor T2 anticipated — the real
number is larger than the earlier ≈2,432 B guess). `queue` server confirmed FAILED (script
missing, pre-existing, not this task's doing) — 0 tools either way. **Decision: leave
`tools.tool_search.enabled` at `"auto"`** — the fixed per-request tax is unconditional and
permanent while the benefit is already-shrinking (Repair 2) and unmeasurable without a forbidden
model call. A complete "no."

**Part 3:** Levers A, B, C applied to `~/.hermes/profiles/david/config.yaml` only (exact
changes/rollbacks recorded above, each measured separately before the next was added). Cumulative:
tools 39,147 → 7,493 B (−31,654 B, 29 → 5 tools); system_prompt 32,191 → 21,725 B (−10,466 B).
Lever D not applied (Part 2's "no"). T1's Repair 1 wording: **left in place**, not reverted — still
true, still partially load-bearing against `tool_search`, cheap, and out of this task's edit scope
beyond this explicit decision.

**Acceptance:** all six T1 cases byte-identical (no regression). Tool-array assertions: both
directions PASS, plus a rehearsed negative case that correctly FAILed, proving the checker isn't a
PASS-only rubber stamp. Native skills catalog confirmed absent three independent ways. Final Fred
request: 72,640 B total (tools 7,493 + system_prompt 21,725 + assembled context/question 43,422) —
**−34.5%** vs. T1's 110,886 B, **−22.8%** vs. the 94,102 B baseline, with one disclosed
instrument-boundary caveat (a ~3,773 B `AGENTS.md/cwd files` tier present in this task's offline
instrument but absent from T1/T2's original captured-request decomposition; constant across every
before/after measurement in this task, so it affects only the absolute cross-instrument comparison,
never any lever's attributed delta).

**Part 4:** no single boundary exists across TTROS's three independent Hermes-invocation shapes
(ad hoc script subprocess calls, the shared shell coordinator, per-profile shell launchers).
Reported per the task's own escape valve rather than scattering a duplicate check into three
files. No code changed.

**Regression:** 828/829 passed (1 pre-existing, named, unrelated permission-gap failure);
population 829, unchanged from T2. `git diff --check` clean apart from the same two pre-existing
whitespace findings. No repo file touched by this task (verified via `git status`).

**The largest remaining fixed cost, named:** the 21,725 B system prompt, of which ~9,753 B is
Hermes's own native framework boilerplate (parallel-tool-call rules, tool-use enforcement,
execution-discipline text) that no per-profile config lever reaches — it is not a TTROS-owned
block and this task's boundaries (config only, no Hermes patching) put it out of reach. Reaching it
would require either a Hermes-side change (out of bounds here) or accepting a Step-8-scale
prompt-restructuring decision that is explicitly not this task's to make.

**The single live acceptance question to run LATER, when quota returns (write, do not execute):**

```
hermes -p david -z "What happened in my meeting with Fred, and what did he say about MLS?"
```

Check, post-run, against `~/.hermes/profiles/david/state.db`: (a) the real provider `input_tokens`
for this call, compared against this task's 72,640 B / ~estimated-token construction, to confirm
the offline instrument's numbers actually match a real dispatched request the way `prompt-size`'s
own docstring promises; (b) `api_calls == 1` with no `skill_view`/`tool_describe` call for content
already inlined (confirming Lever B's structural fix holds live, not just in construction); (c) the
answer still correctly names Fred, MLS/GVR access, and the realtor-workflow content — i.e., that
removing 24 tools did not silently degrade David's actual answer quality on the one question this
whole step's savings are benchmarked against.

**Recommend: PASS**, with the two named, disclosed items above (the cross-instrument
`AGENTS.md/cwd` tier caveat; Part 4's "no single boundary" finding) — not hidden, both explicit
findings rather than gaps swept under. Recommendation only; Liam decides the status.

No commit. No push.

---

## CORRECTION 2026-09-10 (from STEP T4, `scripts/stepT4_post_t3_closeout.md`)

Applied by STEP T4, which re-examined this section's arithmetic against a fresh, zero-model-call
measurement. Full evidence and predictions in `scripts/stepT4_post_t3_closeout.transcript.txt`.
This section corrects, it does not replace, the Part 2 text above — none of that text was edited.

**(a) The break-even arithmetic above was wrong at N=2.** Comparing the 29,400-token fixed tax
(21 questions × 1,400 tokens) against N residual round trips at the ~28,884-token/trip figure
this same Part 2 used:

| N residual round trips | Benefit (N × 28,884) | vs. 29,400-token fixed tax |
|---:|---:|---|
| 1 | 28,884 | tax costs *slightly more* (loses by 516 tokens, ~1.8% — essentially break-even) |
| 2 | 57,768 | tax costs *much less* — **eager wins clearly, not the tax** |

The original text said *"if Repair 2 cut real traffic to even 1–2 residual calls... the fixed tax
exceeds the remaining benefit."* That is correct at N=1 (barely) and **wrong at N=2** (benefit is
roughly double the cost there). Corrected: break-even sits at almost exactly one residual round
trip across a 21-question pass; at two or more, this arithmetic alone favours eager, not lazy.

**(b) The 4,526 B eager cost was priced GROSS, never netted against the bridge triad it replaces.**
`tool_search`/`tool_call`/`tool_describe` (2,551 B in the current live config, measured directly —
see below) exist *only* because `tools.tool_search.enabled` stays `"auto"` (Part 0 of this report
says so explicitly). Turning it `"off"` would remove those three tools, not just add the MCP
array on top of them. Measured on a **copy** of david's profile
(`/home/liam/ttros_backups/stepT4_2026-09-10/david_copy_item4_whatif/`, never the live profile):

| Configuration | Native tools (memory+clarify, bridge removed) | Eager MCP array | Total | Net vs. live 7,493 B |
|---|---:|---:|---:|---:|
| All 10 tools eager (protocol tools included) | 4,942 B | 4,526 B | 9,468 B | **+1,975 B** |
| 6 TTROS tools only (protocol tools excluded) | 4,942 B | 3,440 B (measured) | 8,382 B | **+889 B** |

**The four generic MCP protocol tools (`get_prompt`/`list_prompts`/`list_resources`/`read_resource`)
CAN be excluded natively, per server, with no patch:** `mcp_servers.<name>.tools: {resources:
false, prompts: false}` — `tools/mcp_tool_registration.py:71-89 _select_utility_schemas` (gates on
this exact key, default `true`) and `tools/mcp_tool_schema.py:221-222` (maps `list_resources`/
`read_resource` → `resources`, `list_prompts`/`get_prompt` → `prompts`). **Already live**, right
now, on operator-lean's own `config.yaml` for both its `operator` and `brain` MCP entries — not a
new mechanism. Applying it to the copy was verified empirically (not just read from source): the
array dropped from 10 tools/4,526 B to exactly the 6 TTROS tools/3,440 B, confirmed by name.

**Net corrected: going eager costs +889 B to +1,975 B more than the current live 7,493 B tools
array — never negative.** The prediction this task wrote before measuring ("net change between
-600 B and +1,100 B; negative if protocol tools excludable") was **wrong in sign and partly out of
range**: excluding the protocol tools substantially shrinks the net cost (from +1,975 B to +889 B,
a 55% reduction) but does not make it negative. Reported as measured, not forced to match the
prediction.

**Instrument caveat, disclosed:** `hermes prompt-size` itself could not be used for the eager-array
side of this measurement — when `tools.tool_search.enabled: "off"` is set, its offline
inspection-agent construction shows an unrelated, reproducible anomaly (two native tools never in
david's KEEP set, `session_search` and `todo_list`, appear, while the bridge triad's absence drops
the *native* count to 4 instead of the expected 2) that was isolated (not fully root-caused) to the
literal value `"off"` specifically — `"auto"` and an explicit `"auto"` both reproduce the correct
5-tool baseline. This is an offline-inspection-path anomaly in Hermes v0.21.1, not necessarily a
live-session defect; not investigated further. The NET figures above were computed by combining
the live-measured bridge-triad cost (T3 Part 3's own toolset breakdown: 2,551 B) with the
directly-measured `discover_mcp_tools()`/`registry.get_definitions()` eager array, avoiding
`prompt-size`'s confounded "off" output entirely.

**(c) The ~28,884-tokens-per-round-trip figure is now stale; re-estimated (ESTIMATE, not measured)
at ~11,674 tokens/round-trip post-T3:** that figure was T1's own measurement against the *pre-T3*
request (~40,088 B tools + ~32,191 B system prompt = 72,279 B resent per hop). Post-T3, the same
two components total 7,493 + 21,725 = 29,218 B — a 0.4042× ratio. Scaling proportionally:
28,884 × 0.4042 ≈ **11,674 tokens/round-trip (ESTIMATE)**. This *tightens* the case for staying
lazy, not eager: at the smaller post-T3 per-hop cost, even N=2 residual round trips (23,348
tokens) is still cheaper than the 29,400-token fixed tax, and break-even now sits between N=2 and
N=3, not N=1 as (a)'s correction alone implied. **Net effect of (a)+(b)+(c) together: (a) alone
would have favoured eager at N≥2; (c) reverses that once the per-hop cost is corrected for the
smaller post-T3 prefix — the honest post-T3 break-even needs close to 3 residual round trips, not
1, before eager wins.**

**(d) Coupling check (read-only, no change):** would B6, receipt readers, or the STEP-U
fail-closed/native guard still recognise direct eager brain-tool calls in place of
`tool_call`-wrapped ones? **No coupling risk found.** `scripts/step5_step6_post_repaired_b6_investigation_instrument.py:277,326`
already keys on the *resolved* tool name (`mcp__brain__open_note`/`open_call`), not the literal
`tool_call` wrapper string — consistent with this report's own Part 1 finding that state.db's
message log already unwraps bridged calls to their real target name. `hooks/b7_test_material_guard.py`'s
`BLOCKED_TOOL_NAMES` (STEP U's list) has zero overlap with any `mcp__brain__*` name either way. The
STEP-U fail-closed `RuntimeError` gate in `agent/turn_context.py` checks only for the
`TTROS_ASSEMBLED_CONTEXT_V1` marker in the `pre_llm_call` hook output, entirely independent of
which MCP tools are eager or deferred.

**Revised recommendation:** the corrected arithmetic in (a) and (c) point in opposite directions
at different residual-call counts, and (b)'s real net cost (+889 B to +1,975 B, never negative)
is a small, permanent, unconditional tax regardless. **This still does not clear the bar for
changing the live profile** — the benefit remains unmeasurable without a forbidden model call, the
net eager cost is confirmed positive (not negative, correcting this task's own prediction), and
STEP T4 explicitly did not apply this to david's live config (Item 4's instruction: "DO NOT apply
tool_search changes to the live profile"). T3's original decision (leave `"auto"`) stands, now on
corrected rather than partly-wrong arithmetic, with a materially smaller and better-quantified
margin than either the original text or a naive gross-cost reading would suggest. Liam decides.
