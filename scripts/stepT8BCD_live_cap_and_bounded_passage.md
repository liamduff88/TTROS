# STEP T8-BCD — a real live cap, card pointer -> bounded passage, one capped live turn

**Verdict: PASS on all four Part D acceptance criteria, live-confirmed, in one authorized live
call.** When David needs Fred's exact words and the card doesn't carry them, one tool call from
the card's own pointer now returns the bounded passage — no malformed-pointer retry, no spill,
no keyword-guessing `search_history` loop. Proven offline (7 checks, all PASS) and then in the one
live turn this step authorized (1 of 1 model invocations used).

---

## Part B — a real live cap (zero model calls)

**Invocation shape found:** `hermes chat -q "<question>" --oneshot --max-turns N`, with
`HERMES_HOME=/home/liam/.hermes/profiles/david` selecting the profile (this build has no `-p`/
`--profile` flag, confirmed by T7 and re-confirmed this step). This is a genuine single-query,
non-interactive shape (`--oneshot` "answer the query and exit"), distinct from the `-z`/`--oneshot`
top-level shape T5/T6/T7's contaminating sessions actually used.

1. **Yes, and yes.** `hermes chat` has `--max-turns N` (its own top-level `hermes -z` does not —
   confirmed again this step, matching T7). Traced the CLI wiring directly:
   `hermes_cli/main.py::_CHAT_PASSTHROUGH` passes `args.max_turns` through to `cli.main` →
   `_init_model_routing(..., max_turns, ...)` → `cli.py::_init_turn_limits` sets
   `self.max_turns` (CLI arg takes priority over config/env/default) → session creation stores
   `model_config={"max_iterations": self.max_turns, ...}`. **Live-confirmed this step**: the D
   session's stored `model_config.max_iterations` = **6**, exactly the passed value — this is the
   first time in this step sequence `--max-turns` has been proven to actually bind (T7's Part 0b
   found it silently absent from every prior session).
2. **Yes.** `state.db`'s `sessions` table has `api_call_count`, `tool_call_count`, `started_at`
   (epoch float), `model_config` (JSON) — read directly, session identified by `started_at` after
   the instrument's own launch timestamp (not "latest row" — the instrument logs and checks for
   exactly one new row).
3. **By code, yes; live-confirmed this step too.** The context-plugin hook runs in-process inside
   whichever Python process Hermes launches, regardless of CLI shape, so `TTROS_DAVID_TEST_TURN=1`
   set in the child's `env` is visible to `os.environ.get(...)` inside the hook exactly as for the
   `-z` shape T7 proved. Live proof this step: the vault session-journal sentinel file was
   byte-identical (same sha256, same size) before and after the live D turn — the write-gate held.
4. **`agent.iteration_budget`, seeded from and equal to `max_iterations`** at turn start
   (`agent/turn_context.py:477`, `agent/agent_init.py:2234`: `IterationBudget(max_iterations)`),
   is the actual token-bucket the loop decrements each LLM call (with occasional refunds, e.g.
   `turn_preflight_gate.py`); the loop's continue-condition
   (`agent/conversation_loop.py:1484`) requires *both*
   `api_call_count < max_iterations` *and* `iteration_budget.remaining > 0`. On this shape both
   terms bound the same thing (the number of LLM API-call iterations in the turn) via the same
   number.
5. **Production runner, recorded only, not changed.** `tools/aos-hermes-coordinator.sh` invokes
   David via `hermes -p "$profile" --usage-file "$usage_file" --oneshot "$prompt"` — the **same
   top-level `-p`/`--oneshot` shape T7 already proved does not parse on the currently-installed
   Hermes CLI** (`-p`/`--profile` does not exist on this build; T7's own two failed attempts hit
   this exact error). This means the production coordinator script's own Hermes invocation is
   very likely non-functional against the installed CLI version — a pre-existing, out-of-scope
   finding, named for the record, not fixed here. No `--max-turns` appears in that script at all,
   so production has no per-turn cap beyond whatever `agent.max_turns` resolves to from
   `config.yaml`/env (unproven live, same unbounded situation T7 found).

**Whatever Part B found, Part D still enforced its own hard limits regardless:** 180s wall-clock
kill and exactly one invocation attempt (hard error on a second), both in the instrument itself
(`scripts/stepT8BCD_live_capped_passage_turn.py`), not relied on from Hermes alone.

---

## Part C — one lever: card pointer -> bounded passage

**Recon (read-only, from source):**
- The Fred card (`sources/intake/cards/d9cb4668….card.md`) renders the pointer to its source as an
  Obsidian wiki-link: `[[sources/intake/records/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74|source]]`
  — bare, no `business_brain:` prefix, **no `.md` extension** (Obsidian wiki-links omit it).
  `open_note` passed that exact string, unprefixed and unsuffixed, fails: `tools/brain_memory.py`
  `_safe_relative()` requires a `.md` suffix and raises `"Hermes durable knowledge writes must
  target Markdown"` on anything else — a read-path error inheriting a write-path message, which is
  why T7 saw it as misleading.
- **Hermes's own tool-result spill threshold is 50,000 characters** (chars, not bytes) —
  `tools/budget_config.py::DEFAULT_MCP_RESULT_SIZE_CHARS`, the tighter default applied to any
  `mcp_`-prefixed tool (all of David's brain-MCP tools), capped at `min(mcp_result_size,
  default_result_size)`.
- `open_note`'s own cap is `MAX_NOTE_CHARS = 60,000` chars — **above** the 50,000-char spill
  threshold, so any note truncated to (or near) 60,000 chars still spills at the Hermes layer, as
  T7 observed (60,756-char serialized result).
- `search_calls`/`open_call` bound output the same way (`_truncate(text, MAX_NOTE_CHARS)`,
  60,000 chars) but are hard-scoped to `HISTORICAL_CALLS_DIR = "sources/historical_calls"` —
  structurally unable to reach `sources/intake/records/`, confirmed again this step
  (`open_call("d9cb4668...")` still errors `no such vault note`).

**Lever chosen: gave `open_note` a bounded query mode, plus permissive pointer normalization.**
Not `search_calls`/`open_call`, because (a) those are `call_id`-shaped (a bare slug, no query
parameter, no pointer-format tolerance) and reaching intake records would mean re-scoping their
whole identity, not adding a mode; (b) the acceptance criteria need one function that both resolves
the card's exact literal pointer *and* accepts the question's terms to bound its output —
`open_note` already owns general vault-note reading, so extending it is the smaller, single-purpose
change.

**Exact change** (`tools/brain_memory_mcp.py`):
1. `open_note(pointer, query: str = "")` — new optional `query` param, backward compatible
   (omitted/empty behaves exactly as before).
2. Pointer normalization: strip `business_brain:` (unchanged), then if the final path segment has
   no `.` at all, append `.md` before resolving. A pointer that already carries some other
   extension is left alone (still correctly fails as "must target Markdown" — no behavior change
   there). This alone fixes bare/prefixed × with/without-`.md` — all four forms now resolve with
   no retry.
3. New `_bounded_passage(text, query)`: splits the note into lines, weights each query term by
   `1/occurrences-in-this-note` (a plain per-call inverse-frequency weight — no stopword list, no
   external corpus), scores each line by weighted term hits, and assembles up to `PASSAGE_MAX_CHARS
   = 12,000` chars of the highest-scoring lines plus 2 lines of context each. Returns `None` when
   no line matches any term (never returns an arbitrary chunk). 12,000 chars leaves comfortable
   headroom under the 50,000-char spill threshold even after JSON-wrapper/escaping overhead.
   *(First version scored by raw term frequency; the live participant's own name appearing on
   almost every line — 105 of ~250 — silently drowned out the one line that actually answered the
   question. Caught by the offline proof itself, not assumed away — fixed with the inverse-
   frequency weighting before any live call.)*
4. Docstring updated to name intake records explicitly and say when to pass `query`.

**Backup and rollback — corrected mid-step, recorded honestly:**

The first preimage I saved was pulled from `git show HEAD:tools/brain_memory_mcp.py`. That was
**wrong**: git status at session start already showed `tools/brain_memory_mcp.py` as modified (`M`)
— the working tree already held substantial uncommitted work (the entire Step 6 depth-tools
surface — `search_calls`/`open_call`/`open_note`/`search_history` — plus an MCP-library migration
from `mcp.server.fastmcp.FastMCP` to `mcp.server.mcpserver.MCPServer`) that the last commit does
not contain. A `git`-based rollback would have silently discarded that uncommitted work, not just
this step's own change. Caught before any rollback was ever executed — only the backup file was
wrong, never the working tree — by reconstructing the true pre-edit file from the literal content
this session's own first `Read` of the file captured (verbatim, before any edit), and confirming
`diff(true_preimage, current_file)` shows *exactly and only* this step's intended change (verified
byte-for-byte). The backup was replaced with the correct one before any test ran.

- **Backup (corrected):** `/home/liam/ttros_backups/stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE`
  sha256 `1ffb86059e48c61c34f2aff9fc89ebb38c0f350ae0798427b21c5a6df24bdc6c` (recorded in
  `PREIMAGE.sha256` beside it).
- **Rollback:** `cp /home/liam/ttros_backups/stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE tools/brain_memory_mcp.py`
  — restores the file to its true pre-this-step state, including the pre-existing uncommitted
  Step-6 work, not just to the stale committed HEAD.
- **Named for Liam, not acted on:** `tools/brain_memory_mcp.py`'s last git commit is stale relative
  to the working tree by an entire feature surface. This is one file among the many `M`/`D` entries
  already showing in git status at session start — worth a deliberate commit/review pass, not
  something this step touches (no commit was made; out of this step's authorized surface).

**Server restart:** not needed and none was done. David's `brain` MCP server is a stdio subprocess
(`mcp_servers.brain.command`/`args` in `config.yaml`), spawned fresh per Hermes session — the live
Part D turn loaded this step's edited code automatically.

### Offline proof — predictions written before running, then run (`scripts/stepT8BCD_partC_offline_proof.py`, transcript beside it)

| # | Check | Predicted | Result |
|---|---|---|---|
| 1 | Card pointer, verbatim, BEFORE (true preimage) | fails, `"...must target Markdown"` | **PASS** — fails exactly as predicted |
| 2 | Card pointer, verbatim, AFTER | succeeds | **PASS** |
| 3 | GVR-boards query via card pointer | contains `"I think 11 boards"`; serialized size strictly < 50,000 chars | **PASS** — content 11,970 chars, serialized 12,380 chars |
| 4 | Negative control, query=`"unicorn"` (verified absent, `grep -c -i` → 0) | no passage, not an arbitrary chunk | **PASS** — `matched:false`, `content:""` |
| 5 | `open_call` on a historical call, before vs after | byte-identical | **PASS** — identical (47,441 chars both) |
| 6 | T1's six `assemble()` cases vs T7's last-reported baseline | zero byte delta | **PASS** — all six: delta `+0` |
| 7 | `hooks/context_assembler_hook.py` mode | still 755 | **PASS** — 755 |

**Full suite:** `829 passed, 1 skipped, 0 failed` (393.76s,
`PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest`). Same
829-passed population T7/T8-A last reported (772/746/760 are the stale figures CLAUDE.md already
flags). The 1 skip is this step's own new test file
(`tests/test_brain_memory_mcp_intake_passage.py`) — it imports `mcp.server.mcpserver`, which only
Hermes's own venv has installed, not the dashboard test venv; it `pytest.importorskip`s cleanly
(confirmed: 10/10 pass under Hermes's venv, which does have that package) rather than erroring.

---

## Part D — one capped live turn

**Question (verbatim):** "In my meeting with Fred, what were his exact words about how many GVR
boards there are?"

**Offline pre-check, this step, zero model calls:** `assemble()` for this exact question does
**not** contain `"11 boards"` in its rendered context (re-confirmed fresh, matches T8-A) —
provenance was therefore a real test, not a foregone conclusion.

**Prediction (written before the call, both outcomes pre-registered as plausible):** bimodal —
(a) if David passes `query` to `open_note` on the card's pointer, ~2 calls, bounded, no spill; (b)
if David omits `query` (falls back to the old full-truncated 60,000-char content, still above the
50,000-char spill threshold), the old spill-then-`search_history`-guessing pattern likely recurs
and fails the ceiling, as in T7's D2. This step's docstring change can only *encourage* query use —
it cannot force a live model's tool-call shape.

**Live result — session `20260910_215051_018982`, 1 of 1 authorized model invocations, 18.3s
elapsed (well under the 180s kill), `--max-turns 6` passed and `model_config.max_iterations`
recorded as **6** (the first live proof in this step sequence that the flag actually binds):**

Itemised call list (`api_call_count=3`, `tool_call_count=2`):
1. `tool_describe(mcp__brain__open_note, ...)`
2. `mcp__brain__open_note` — called **once**, directly on the card's bare pointer, with a `query`
   (reasoning trace shows `mcp__brai… GVR boards`) — case (a) of the prediction. No malformed-
   pointer retry, no spill, no `search_history` calls at all.
3. (final assistant turn)

**Acceptance, each criterion:**
1. Answer contains "I think 11 boards": **PASS** — verbatim in the response.
2. Provenance (a tool result *in this turn* returned the passage from Fred's intake record, not a
   prior session): **PASS** — the `mcp__brain__open_note` tool result itself contains both
   `"I think 11 boards"` and the Fred record's pointer/hash; checked the actual stored tool-result
   text in `state.db` `messages`, not the tool name.
3. `api_calls ≤ 4`: **PASS** — actual 3, itemised above (2 tool calls: `tool_describe` +
   `open_note`, plus the model's own final-answer call).
4. Vault journal unchanged after the turn: **PASS** — `sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md`
   byte-identical (same sha256 `744346...`, same 493-byte size, same mtime) before and after; so is
   `sessions/thread_david.md`.

**OVERALL: PASS on all four criteria**, on the first and only authorized live attempt.

---

## What this licenses

- A real, live-proven invocation shape (`hermes chat -q ... --oneshot --max-turns N` +
  `HERMES_HOME`) whose turn cap is genuinely enforced and machine-readable after the fact
  (`model_config.max_iterations` in `state.db`) — the first time in this step sequence any
  `--max-turns` value has been shown to actually bind a real session, superseding T7's Part 0b
  finding that it never had been.
- A working card-pointer → bounded-passage retrieval path for `sources/intake/records/`: the exact
  pointer a source card renders now resolves on the first call, in any of the four
  bare/prefixed × with/without-`.md` forms, and a query-scoped call returns a small, verifiably
  bounded excerpt containing the actual matching words — proven offline (7/7 checks) and once live
  end-to-end, with correct provenance and well inside the call-count ceiling.
- Confirmation the fix is general, not hand-fit to Fred's record: the offline proof's negative
  control (a verified-absent term) returns no passage rather than a fallback chunk, and the
  inverse-frequency weighting was validated against a case (a speaker's own name dominating raw
  frequency) that a naive implementation would have gotten wrong — caught and fixed before the live
  call, not discovered by it.
- The production coordinator's own Hermes invocation shape (`-p "$profile" --oneshot`) is very
  likely broken against the currently-installed Hermes CLI (no `-p`/`--profile` flag exists) — a
  real, actionable, pre-existing finding surfaced as a side effect of Part B's recon, named for
  Liam, not fixed here (out of this step's authorized surface).

## What this does not license

- **Not a guarantee David will always choose to pass `query`.** The docstring change can only
  encourage bounded reads for large intake sources; it cannot force a live model's tool-call shape.
  This step's live call happened to land in the favorable case on its one authorized attempt; the
  unfavorable case (query omitted, old spill-then-guess pattern recurring) was pre-registered as
  equally plausible and was not exercised live — a second live turn could still show it, and this
  step does not claim otherwise.
- **Not a fix to `--max-turns`'s reliability on every shape** — only the `chat -q --oneshot` shape
  was tested; the top-level `-z`/`--oneshot` shape (what production's coordinator script and all of
  T5/T6/T7's contaminating sessions actually used) still has no proven cap, and per Part B, cannot
  even accept `--max-turns` as a flag on this installed Hermes build.
- **Not a repair of `tools/brain_memory_mcp.py`'s stale git history** — the file's last commit
  predates an entire feature surface that exists only in the uncommitted working tree; this step
  named that fact (caught while building this step's own backup) but did not commit, review, or
  otherwise act on it.
- **Not a claim that `search_calls`/`open_call`'s scope gap is closed** — they remain unable to
  reach `sources/intake/records/`; this step's lever lives entirely in `open_note`, by design (see
  "lever chosen" above).

## Files

- Code change: `tools/brain_memory_mcp.py`
- Tests: `tests/test_brain_memory_mcp_intake_passage.py` (10 tests, pass under Hermes's venv;
  skip cleanly under the dashboard test venv, which lacks the `mcp` package)
- Offline proof + transcript: `scripts/stepT8BCD_partC_offline_proof.py` /
  `scripts/stepT8BCD_partC_offline_proof.txt`
- Live-turn instrument + transcript: `scripts/stepT8BCD_live_capped_passage_turn.py` /
  `scripts/stepT8BCD_live_capped_passage_turn.txt`
- Backup: `/home/liam/ttros_backups/stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE`
  (sha256 in `PREIMAGE.sha256` beside it)

**Model invocations made this step: 1 (declared max: 1).** No vault writes. No git commit, no
push. No restart of any service.
