# STEP T7 — test-turn isolation and bounded missing-fact retrieval

Reads `scripts/stepT6_live_overretrieval_repair.md` Parts A, C, D as given; T1-T5 not re-derived.
Transcript tee'd at `scripts/stepT7_test_isolation_and_bounded_retrieval.transcript.txt`
(refuses to overwrite).

---

## PART 0 — INTEGRITY (zero model calls)

### 0a — every David session since 2026-09-10 15:50 PDT

Queried `/home/liam/.hermes/profiles/david/state.db` `sessions` directly (`started_at >=
1789080600`, the epoch for 2026-09-10T15:50:00 America/Los_Angeles):

| id | started (PDT) | api_calls | tool_calls | title |
|---|---|---:|---:|---|
| `20260910_155322_c8eda5` | 15:53:24 | 11 | 14 | Summarize meeting with Fred (T5) |
| `20260910_164259_695793` | 16:42:59 | 1 | 0 | Summarize meeting with Fred #2 (T6-D1) |
| `20260910_164318_637846` | 16:43:19 | 9 | 12 | Identify Fred Haiderzada MLS platform (T6-D2) |

**Exactly three — matches the expected T5/T6-D1/T6-D2 set. No other finding.**

### 0b — did the first pass's D2 invocation carry `--max-turns 6`?

Settled directly from each session's own stored `model_config` (not from the step script's
declared intent, which is a different thing from what actually ran): all three sessions above —
including D2, which made 9 provider requests — show
`"max_iterations": 9223372036854775807` (`sys.maxsize`, Python's "unbounded" value), not `6`, and
not even the profile's own `config.yaml` default (`agent.max_turns: 150`).

Traced through the live Hermes v0.21.1 source (`/home/liam/.hermes/hermes-agent/`, editable
install): `--max-turns` (`hermes_cli/_parser.py:250`) flows through `cli.py:_init_turn_limits` →
`self.max_turns` → `AIAgent(max_iterations=self.max_turns)`
(`hermes_cli/cli_agent_setup_mixin.py:521`) → the turn loop's own gate,
`agent/conversation_loop.py:1484`:
`while (s.api_call_count < agent.max_iterations and agent.iteration_budget.remaining > 0) or
agent._budget_grace_call:`, with `api_call_count` incremented once per iteration in
`turn_iteration_prep.py:347` before the next check. Reading that loop, a real `--max-turns 6`
**would** stop at exactly 6 iterations — there is no separate uncapped provider-request counter;
the `api_calls` field written to `--usage-file` is the same `api_call_count` this loop bounds
(`agent/turn_finalizer.py:540`, `hermes_cli/oneshot.py:30`).

**Verdict: the flag was ABSENT from the first pass's actual invocations, not present-but-
ineffective.** All three sessions carry the "unlimited" sentinel, meaning no invocation in the
first pass passed `--max-turns` at all (T6's own script, which does pass `--max-turns 6`, was
never actually executed for these three sessions — T6's own report already established this:
the first pass's turns predate the script being run, refusing to overwrite its own transcript).
**Part D's cap in this step is therefore NOT proven effective by any live observation** — it is
a plausible-by-code-reading mechanism that has never actually been exercised. Per this step's own
instruction, Part D treats `--max-turns` as advisory only and enforces the real ceiling in the
instrument itself (hard-stop after turn 1 if its own `api_calls > 6`).

---

## PART A — every channel by which a test turn reaches David later (zero model calls)

**(i) Assembler session-recency block** — `tools/context_assembler.py:_session_recency_block`
(function at line 821). Reads every `*.md` under `vault_root/sessions/` with frontmatter
`type: session` and matching `client_scope`, splits on `### Turn · <timestamp>` headers, scores
each turn by query-term/work-item-id overlap (`RECENCY_FLOOR`), and selects the **2 most recent**
qualifying turns — recency-first, no relevance ranking beyond the floor, and **no filter of any
kind for test/harness origin.** Source: the vault's own `sessions/*.md` day-files (written by (iii)
below). T5/T6 turns are IN this pool today (confirmed live below).

**(ii) `mcp__brain__search_history`** (`tools/brain_memory_mcp.py:211`) — full-text search via
`aos_indexer.search(query, source="business_brain", ...)`, i.e. the **whole Business Brain vault
FTS index**, not just historical calls. `tools/aos_indexer.py`'s exclusion lists
(`PROTECTED_SEGMENTS`, `PROTECTED_PATH_PARTS`) exclude `.git`, `north_shore_sales_coach`,
`connectors/telegram_bridge`, secret-looking paths, etc. — **`sessions/` is not excluded.**
T5/T6 turns are therefore fully indexed and returnable by `search_history` once written.

**(iii) `hooks/context_assembler_hook.py` writes for profile `david`** — confirmed as the
write path for both (i) and (ii)'s corpus. `"david"` is in both `THREAD_PROFILES` (gets
`write_thread` → supersedes `sessions/thread_david.md` every turn) and `JOURNAL_PROFILES` (gets
`append_session_turn` → appends to `sessions/<UTC-date>_hermes-cli_<hash>.md`), **unconditionally
before this step** — no test marker existed. Cross-checked against `state.db`'s own
start/end timestamps (converted to UTC) against the vault file's turn headers: T5
(22:53:24–22:54:12 UTC) → turn at `22:54:12.282800Z`; T6-D1 (23:42:59–23:43:15 UTC) → turn at
`23:43:14.377494Z`; T6-D2 (23:43:19–23:44:03 UTC) → turn at `23:44:01.549610Z`. **All three test
turns were written to both the journal and (superseding) the thread.** Confirmed by direct
timestamp correlation, not by inference from a comment.

**(iv) Native memory (`MEMORY.md`)** — `memory.memory_enabled: true` in david's `config.yaml`,
and `memory` is one of David's 5 visible native tools (T6 A4). Checked
`/home/liam/.hermes/profiles/david/memories/`: contains only an empty `MEMORY.md.lock`
(0 bytes, last touched 2026-08-04) — **no `MEMORY.md` content file exists.** Native memory was
not actually exercised by T5/T6-D1/T6-D2 and is not a live contamination channel today, but it
is reachable and untouched by this step's write-gate (which only covers the vault thread/journal,
per this step's authorized surface) — a real, currently-latent gap, named for the record.

**(v) other** — `session_search` (Hermes's own native cross-session search) was the T6/A3
mechanism, already disabled for David by T6's still-live C1 fix
(`agent.disabled_toolsets: [..., session_search]` in `config.yaml`). Confirmed off; not re-tested
live since T6 already did (D1/D2 both showed zero `session_search` calls).

**Existing test-marking mechanisms found and evaluated:**
- `hooks/b7_test_material_guard.py` gates on `TTROS_BRAIN_ROOT` — but B7's own harness script
  (`scripts/step3_b7_harness.py:515`) sets `TTROS_BRAIN_ROOT` to a **whole separate scratch vault
  copy** (`WORK_VAULT`, rsync'd from a snapshot before every call), so B7 sessions never touch the
  real vault's `sessions/` directory at all — confirmed empirically: the real vault's
  2026-09-10 day-file has no turns in the 2026-09-09T19:01–19:19 PDT window where a batch of
  clearly B7-shaped session titles (`"Did Andrea Roberts introduce us to anyone? #2"`, etc.) exist
  in `state.db`. **B7 is already isolated from the real vault by a different, working mechanism**
  (full vault redirection) — not reusable here (T5/T6/T7 turns deliberately run against the REAL
  vault, since the point is to test real retrieval, not a scratch copy), and out of scope per this
  step's own "NOT AUTHORIZED: ... B7" boundary.
- `SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL` pattern (`hooks/context_assembler_hook.py:35`) — a plain
  `os.environ` sentinel checked inside the hook, gating one profile's behavior. **This is the
  reusable shape** (see Part B).

**PREDICTION (written before Part A) — assessed:** recency and search_history do both draw on
unfiltered David session history (confirmed); T5/T6 turns were written to both the thread and the
journal (confirmed); no existing marker excludes them (confirmed — B7's mechanism is a different
vault entirely, not an exclusion filter on the real one). Prediction holds in full.

**D1 recency fragment's actual source, settled** (T6 said "T5's own prior turn"; this step reads
the actual manifest, not the claim): `queue/context_assemblies/hermes-20260910_164259_695793-...json`,
block `"relevant session recency"`, contains **two** selected turns, both physically inside
`sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md` (UTC-dated file spanning both PDT days):
1. `episodic_relevance=36`, turn `2026-09-10T22:54:12Z` — **T5's own turn**, as T6 said, but this
   excerpt (9 of 24 paragraphs) does **not** include the "11 boards" sentence itself.
2. `episodic_relevance=24`, turn `2026-09-10T00:52:29Z` (= **2026-09-09T17:52:29 PDT**, an entirely
   separate, earlier session) — verbatim: *"Fred's number was: 'like, I think 11 boards.'"* This
   turn belongs to session `20260909_175150_486fe1`, titled **"Find Fred Haiderzada GVR board
   details"** — the exact session T6's own A3 named as a `session_search` hit, now shown to also
   be reachable via plain recency, a day-boundary artifact of UTC-dated vault files holding
   PDT-evening test turns from the *previous* day. **Correction to T6: the forbidden "11 boards"
   quote in D1's answer came from this earlier 2026-09-09 research turn, not from T5's own turn.**
   Both turns are test/research residue; neither is ordinary conversational continuity.

A third, even earlier turn in the same file (`2026-09-10T00:15:18Z` = 2026-09-09T17:15:18 PDT,
session `20260909_171419_ab8c70`, "Realtor workflow dashboard and MLS reporting") is also
manual-research-shaped ("Cite the source") but did not score into D1's top-2.

---

## PART B — repair 1: test-turn isolation

**Mechanism:** one new env sentinel, same pattern as `SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL`:
`TTROS_DAVID_TEST_TURN` (`hooks/context_assembler_hook.py`, `DAVID_TEST_TURN_ENV_SENTINEL`).

**Exact change** — `hooks/context_assembler_hook.py`:
- Added the constant and its rationale comment (profile-scoped to `"david"` only).
- `post_llm_call`: `is_test_turn = profile == "david" and os.environ.get(DAVID_TEST_TURN_ENV_SENTINEL) == "1"`.
- `write_thread(...)` call gated: `if thread_body and profile in THREAD_PROFILES and not is_test_turn`.
- `append_session_turn(...)` call gated: added `and not is_test_turn` to its existing condition.

**Rollback:** `/home/liam/ttros_backups/stepT7_2026-09-10/context_assembler_hook.py.PREIMAGE`
(sha256 recorded in `PREIMAGE.sha256` in the same directory; restore by copy).

**Why suppressing the write is sufficient for (a) *and* (b):** a turn never appended to
`sessions/*.md` or superseded into `thread_david.md` cannot later be selected by
`_session_recency_block` (which only scans files actually on disk) or returned by
`search_history` (an FTS index over files actually on disk). No second, assembler-side exclusion
list is needed — closing the one shared write path closes both downstream read paths at once, for
any *future* marked turn.

**Proof, zero model calls** — `scripts/stepT7_test_isolation_proof.py` (tee'd transcript beside
it), calling `context_assembler_hook.evaluate()` directly (the same function Hermes's hook
invokes), mocking `write_thread`/`append_session_turn`, both directions on the identical
topic/profile:
- Marked (`TTROS_DAVID_TEST_TURN=1`): `write_thread.called=False`,
  `append_session_turn.called=False` — **PASS**.
- Unmarked (otherwise identical): `write_thread.called=True`, `append_session_turn.called=True`
  — **PASS**. (A detector that could only print PASS on the marked case would prove nothing; both
  directions were required and both were run.)

**T1's six `assemble()` cases, re-run against the current tree:**

| Case | scoped-note-block bytes | delta from T6 post-C2 |
|---|---:|---:|
| Fred/MLS | 5,148 B | 0 |
| CCI | 7,444 B | 0 |
| Andrea | 4,833 B | 0 |
| Negative control 1 | 192 B | 0 |
| Negative control 2 | 192 B | 0 |
| Fallback control | 192 B | 0 |

Zero delta on every case, exactly as expected: this step's fix lives entirely in
`hooks/context_assembler_hook.py`'s `post_llm_call` write path and never touches `assemble()`,
`_scoped_note_block`, or `_session_recency_block`. No residue was excluded by this mechanism (see
below), so there is nothing for `assemble()` to differ on.

**Full suite, run this step:** `829 passed, 0 failed, 223 subtests passed` (384s) —
`PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest`. Same
population as T6's own last-reported run (829), so no regression and nothing silently dropped.

### Existing residue — NOT excluded, NOT rewritten (per this step's authorization)

Checked whether existing test turns could be excluded from recency/search "by the same mechanism"
keyed on session id: **no.** `tools/brain_memory.py::append_session_turn` and `write_thread`
embed only a UTC timestamp in the turn body (`### Turn · <stamp>`) — no session id is ever written
into the vault text itself (confirmed by reading both functions, lines 456–543). Keying on session
id is therefore impossible without inventing a new id→turn registry, which this step's own
instruction rules out ("otherwise write a plan for Liam"). **No code change was made for existing
residue.**

**Residue, listed** (`sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md`, vault-relative path under
`TTROS Business Brain/`):

| Lines | Turn timestamp (UTC) | Session (state.db id) | Nature |
|---|---|---|---|
| 20–97 | 2026-09-10T00:15:18Z | `20260909_171419_ab8c70` | Pre-T5 manual research ("Cite the source") |
| 98–125 | 2026-09-10T00:52:29Z | `20260909_175150_486fe1` | Pre-T5 manual research — **confirmed direct source of D1's forbidden "11 boards" quote** |
| 126–190 | 2026-09-10T22:54:12Z | `20260910_155322_c8eda5` (T5) | T5's own live-proof turn |
| 191–246 | 2026-09-10T23:43:14Z | `20260910_164259_695793` (T6-D1) | T6-D1's own turn (already contains the forbidden claim it received) |
| 247–end | 2026-09-10T23:44:01Z | `20260910_164318_637846` (T6-D2) | T6-D2's own turn |

`sessions/thread_david.md`: superseded (not appended) on every write, so it currently holds only
whatever the last real write left there (T6-D2's content) — not append-only residue; it will be
naturally overwritten by the next real (unmarked) David turn and needs no cleanup action.

**Cleanup PLAN for Liam (not executed this step):**
1. Once Liam confirms none of the 5 turns above hold durable value, delete lines 20 through
   end-of-file from `sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md` (keep the 1–19 frontmatter/
   header), as a normal manual vault edit + git commit outside Hermes's own write-transaction path
   (this file is a plain vault note; `write_transaction`'s hash-guard only fires on Hermes's own
   writes, not manual edits) — restores the file to a clean pre-2026-09-09 state without touching
   `write_transaction`'s locking contract.
2. Lighter alternative: leave the 5 turns in place but manually prepend a one-line marker
   (e.g. `> TEST/RESEARCH TURN — not conversational continuity`) to each, so a human reader
   recognizes them; this does **not** stop recency/search_history from surfacing them (the
   mechanism built this step only prevents *future* writes, it does not filter existing text by
   content), so it is a documentation aid only, not a technical fix.
3. Recommended: option 1, since these 5 turns are actively contaminating today's retrieval (as
   Part D below will show) and hold no standalone business value beyond what the underlying
   Fred source record and its card already preserve.

---

## PART C — bounded missing-fact retrieval

**Diagnosis, from `state.db` session `20260910_164318_637846` (T6-D2), all 22 messages read
directly:**

| Call # | Action | Result |
|---|---|---|
| 1 | `tool_describe([open_note, search_history])` | schemas |
| 2 | `open_note("sources/intake/records/d9cb...")` (bare pointer, no prefix) + `search_history("collaboration center" Fred MLS notification opened)` in parallel | `open_note` → `{"success": false, "error": "Hermes durable knowledge writes must target Markdown"}` (malformed pointer — wasted call); `search_history` → 8 unrelated snippets |
| 3 | `open_note("business_brain:sources/intake/records/d9cb....md")` (corrected pointer) | **success, but the record is 60,756 characters (59.3 KB) — spills**: `"This tool result was too large... Full output saved to: .../cache/spillover/call_....txt. Use the read_file tool with offset and limit..."` |
| 4–9 | Six more `search_history` calls, narrowing/guessing keywords (`"last notification" "collaboration center"`, `"opened" "collaboration center" "Fred"`, `Paragon/Matrix/"MLS Touch" "collaboration center"` in parallel, `"Paragon" "Fred" "notification"`, `"Matrix" "Paragon" "MLS Touch" "Fred"`) | Mostly unrelated hits (a Kenneth/Ollie call card kept ranking); the **last** call (#9) finally FTS-matched the right passage in the Fred record and let David answer correctly |

**PREDICTION (written before this diagnosis) — assessed:** "the raw record is too large for
`open_note` to be usable, so David falls back to repeated `search_history`" — **confirmed**, and
sharper than predicted: the spillover message's own recovery instruction ("Use the `read_file`
tool with offset and limit") **names a tool David does not have** — `file` is in David's
`disabled_toolsets` (`config.yaml`). David cannot follow the system's own recovery instructions
after a spill; blind `search_history` keyword-guessing was the *only* path left, which is why it
took 7 more calls.

**Comparison with the designed Step-6 passage route, tested empirically this step** (zero model
calls, direct Python call against the live `brain_memory_mcp` module):
```
search_calls("Paragon collaboration center Fred", limit=5)
  → matches an unrelated Kenneth/Ollie call card; the Fred record never appears
open_call("d9cb4668...")
  → {"success": false, "error": "no such vault note: sources/historical_calls/d9cb....md"}
```
**The passage route is broken for this whole class of source.** `search_calls`/`open_call` are
hard-scoped to `HISTORICAL_CALLS_DIR = "sources/historical_calls"`
(`tools/brain_memory_mcp.py:146,178`); Fred's meeting is a semantically-ingested source living
under `sources/intake/records/` — a different directory the Step-6 passage tools were never built
to reach. This is true for *every* source ingested through the STEP I2/I3 semantic pipeline, not
just Fred's.

**Per this step's own instruction — "Do not change brain MCP tool behaviour or result limits in
this step unless the diagnosis shows the passage route itself is broken — then STOP this part and
report" — the passage route IS shown broken, so no fix is applied in this step.** No preamble
wording change was made either: pointing David at `search_calls`/`open_call` for an intake record
would be actively wrong (a route proven not to reach it), and the honest "smallest fix" the
diagnosis supports does not exist within this step's authorized surface (it would require either
extending the passage tools' scope to `sources/intake/records/`, or fixing the spillover
message's tool recommendation to something David actually has — both are brain-MCP/Hermes
behavior changes, out of bounds here).

**Recorded, not fixed — T6 A1's truncation, settled:** the ellipsis truncation ("said a
real-estate project management workflow with transaction checkpo…") is **in the card file on
disk** (`sources/intake/cards/d9cb4668....card.md:38-62`, confirmed by direct read), not applied
during context assembly. A separate, pre-existing card-completeness defect, unrelated to test
contamination.

**T1's six `assemble()` cases:** unaffected by Part C (no code change applied); same byte counts
as reported in Part B. **Full suite:** unaffected by Part C for the same reason.

---

## PART D — live proof, two turns

Instrument: `scripts/stepT7_live_test_isolation_and_bounded_retrieval.py`. Both turns run with
`TTROS_DAVID_TEST_TURN=1` in the invocation's own environment (Part B's marker). `--max-turns 6`
is passed but not relied on (Part 0b: never proven live) — the instrument itself hard-stops
before turn 2 if turn 1's own `--usage-file` `api_calls > 6`.

### D1 — Fred/MLS, verbatim as T5, PRE-REGISTERED before running

**Offline check, this step, zero model calls** (`tools.context_assembler.assemble()` called
directly against the live tree, identical to how David's real pre-model context is built):
`"11 boards"`, `"fraser valley"`, `"surrey"`, `"langley"` are **all absent** (case-insensitive)
from the full rendered context as of now. The session-recency block currently selects the **two
most recent** matching turns — which are now T6-D1's and T6-D2's *own* turns (23:43:14Z,
23:44:01Z), having displaced T5's turn and the 2026-09-09 research turn from the top-2 purely by
being more recent. T6-D1's own turn *does* contain the forbidden quote somewhere in its full
text, but the paragraph-level excerpt selector (matching THIS query's terms, which do not include
"GVR"/"boards"/city names) did not pull that specific paragraph in this time. This is incidental
aging-out of contamination via recency ranking, **not** a repair made in this step — Part B's own
write-gate does not touch pre-existing residue at all (see above), and nothing here guarantees
this holds for a different query.

**Required facts** (from the assembled "scoped canonical Brain notes" card block, unaffected by
residue):
1. Fred forwarded the SnapStats sheet during the meeting.
2. An open question remained about what MLS or GVR data access would be available.
3. Fred preferred exploring a project-management-style transaction/workflow dashboard.
4. A SnapStats-style dashboard could potentially be built and sold to other realtors.

**Forbidden claims:** the GVR board count/number, or the Fraser Valley/Surrey/Langley city
names/quote; no CCI/Andrea Roberts content.

**Predicted:** `api_calls` ≤ 2 (target 1, matching T6-D1's own zero-tool-call result for the
identical question); no `search_history`; every required fact present; forbidden claims **absent**
(predicted PASS this time, per the offline check above — not because residue was removed, but
because it no longer scores into this specific query's excerpt).

### D2 — over-suppression control, PRE-REGISTERED before running

Question: "In my meeting with Fred, what were his exact words about how many GVR boards there
are?" — verbatim as T6's own original D2 question (not the question T6's *actual* D2 asked,
which drifted to the MLS-platform-name question; this step asks the pre-registered GVR-board
question directly, since Part C's diagnosis already fully covers the MLS-platform retrieval
path).

**Offline-confirmed this step:** the card block does not contain the "11 boards" quote (per T6's
own A1 finding: the card is ellipsis-truncated exactly here). The current recency block (per the
D1 check above) also does not surface it for a differently-worded query, but D2's own wording
("GVR boards") is exactly the terms that scored the old residue turns highly for T6's D1 — so D2
may well pull the 2026-09-09 research turn or T6's own turns back into its recency block, this
time *with* the quote. **This is not a failure mode this step's mechanism is designed to catch**:
Part B only gates *new* writes; it does not filter existing residue out of recency for a query
that matches it.

**Predicted:** given Part C's finding that the passage route (`search_calls`/`open_call`) is
architecturally unable to reach this record, and no fix was applied (correctly, per this step's
own instruction), David's most likely paths are (a) the same `open_note`-spill-then-search_history
pattern as T6's actual D2 (predict `api_calls` in the 6-9 range, likely exceeding the ceiling and
triggering this instrument's hard-stop before it completes), or (b) the recency block itself
already supplies the quote (0 tool calls, but then likely **FAILS** on provenance if the quote is
traceable only to old residue rather than a live tool read this turn). Both outcomes are
pre-registered as plausible; a genuine improvement is not expected here since Part C's smallest
authorized fix could not be applied.

### Instrument defect found before any live call (zero model calls, not counted as a turn)

First execution of `scripts/stepT7_live_test_isolation_and_bounded_retrieval.py` used
`hermes -p david -z ...` — the same flag T6's own script used. Both invocations failed at
argparse, before Hermes did anything: `hermes: error: argument command: invalid choice: '6'`.
The installed Hermes CLI (`which hermes` → `/home/liam/.local/bin/hermes`) has **no `-p`/
`--profile` flag at all** (confirmed via `hermes --help`'s full options list) — profile selection
in this build is via the `HERMES_HOME` environment variable (the same variable
`hooks/context_assembler_hook.py::_profile()` reads, and the same one every test in
`tests/test_hermes_context_plugin.py` sets). Both failed attempts made **zero model calls**
(`--usage-file` was written empty, `{}`, and no new session appeared in `state.db`) — this is an
instrument defect (wrong CLI flag, per the standing rule "treat the instrument as the likeliest
source of error"), not a live turn that ran and failed a criterion, so it is not counted against
this step's two-turn budget. **Likely explains Part 0b's finding too**: if T6's own scripted
invocation with `-p david` never actually worked against this Hermes build, the real sessions
that produced T5/T6-D1/T6-D2 must have been run some other way (interactive session with
`HERMES_HOME` set, most plausibly) — consistent with none of them showing a bounded
`max_iterations`.

**Fix 1:** `env["HERMES_HOME"] = "/home/liam/.hermes/profiles/david"` in place of `-p david` in
argv. Verified zero-cost first (`hermes status` with that env var → `Model: gpt-5.5`, matching
david's `config.yaml`, confirming correct profile resolution) before spending a live call.

**Second instrument defect, also caught before any live call (zero model calls):** with `-p`
removed, the retry still failed identically (`invalid choice: '6'`) because **`--max-turns` does
not exist on the top-level `hermes -z PROMPT` oneshot parser at all** in this installed build —
confirmed via `hermes --help` (no `--max-turns` anywhere in the top-level options) versus
`hermes chat --help` (`--max-turns N` exists there, but only under the `chat` subcommand, which
in turn has no `--usage-file` — that flag is documented as "No effect outside -z/--oneshot," i.e.
top-level-only). The two flags this step needs together (`--usage-file` for machine-readable
`api_calls`, `--max-turns` for a live cap) **do not coexist on any single Hermes invocation shape
in this build.** This sharpens Part 0b further: it is not merely that `--max-turns` was never
passed to the sessions that produced T5/T6-D1/T6-D2 (all three used the top-level oneshot shape,
per their `source: "cli"` / `billing_provider: "openai-codex"` fields matching this shape, not
`chat`) — **the top-level oneshot invocation these sessions actually used cannot accept
`--max-turns` at all**, on any build matching this installed version. T6's own script's
`--max-turns 6` argument was therefore silently impossible from the start, not merely unproven.

**Fix 2:** drop `--max-turns` entirely from argv; rely solely on this instrument's own
post-hoc hard-stop-before-turn-2 rule (`--usage-file`'s `api_calls` checked after turn 1
completes, before turn 2 is allowed to start) — which is what Part 0b's own instruction already
specified for the "not proven to bind" branch, now confirmed to be the *only* available
enforcement for this invocation shape, not merely the cautious choice.

### Live results

**D1** — session `20260910_174150_08ed71`. `api_calls: 6`. Tool trace: `tool_describe(open_note)`,
`open_note` (bare pointer, malformed — reused the exact same wrong-then-right pointer pattern as
T6-D2), `open_note` (corrected pointer), `tool_describe(search_history)`,
`search_history("Fred MLS Paragon Collaboration Center SnapStats GVR notifications opened")`.
Answer covers all four required facts (SnapStats sheet forwarded, open MLS/GVR data-access
question, preferred project-management workflow dashboard, dashboard-resale idea floated) plus
correct extra detail (Paragon, Collaboration Center). **Forbidden claims absent**: no "11 boards",
no Fraser Valley/Surrey/Langley — confirmed by direct text search of the answer. **FAILS** on
`api_calls ≤ 2` (actual 6) and "no `search_history`" (one call made).

**Named cause:** not new contamination and not a fix regression — a re-manifestation of T6's own
already-reported, not-fully-closed gap (T6's verdict: "C1 and C2 ... do not fully close the
over-retrieval problem"). SOUL.md's "read sources before claims that depend on organisational
history" instruction still drove David to independently open and verify the raw record and search
for corroborating detail even though the assembled context (card + recency block) already
contained everything needed — this step made no change to SOUL.md, the assembler's preamble
wording, or brain MCP tools, so this behavior is unchanged from T6, reproduced faithfully rather
than newly introduced.

**D2** — session `20260910_174229_6495d2`. `api_calls: 8`. Tool trace:
`tool_describe(open_note)`, `open_note` (bare pointer, malformed), `open_note` (corrected — spills
again: same 59.3 KB-too-large pattern as T6's D2), `tool_describe(search_history)`,
`search_history("\"11 boards\" Fred GVR")`, `search_history("\"GVR\" \"boards\" \"think\"
\"Fred\"")`, `search_history("\"like, I think 11\"")` — the last call's top hit is
`business_brain:sources/intake/records/d9cb...md` (Fred's real raw source), not any session file.
Answer: *"like, I think 11 boards"* — **correct**, and **provenance-confirmed from the real source
record**, not from residual test-session content (checked the actual FTS match, not just the
tool name). **FAILS** on `api_calls ≤ 4` (actual 8); **PASSES** "quote correct" and "retrieved
from Fred's source, not a prior session."

**Named cause:** exactly Part C's diagnosis, reproduced (expected — no fix was applied, correctly,
because Part C's diagnosis showed the passage route itself is broken and this step's own
instruction says stop and report rather than force a change to brain MCP tool behavior). Same
open_note-spills-then-search_history-keyword-guessing pattern as T6's original D2, same 59.3 KB
spill size, same 2-of-8-calls wasted on the malformed-then-corrected pointer.

### Post-D isolation check (zero model calls, both directions)

Neither D1 nor D2 wrote to the vault: `sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md` mtime
(2026-09-10 16:44:01 -07:00) and line count (259) are **unchanged** from before both live calls
(D1 ran ~17:41 PDT, D2 ~17:42 PDT — both strictly after 16:44) — direct proof neither
`append_session_turn` nor `write_thread` fired. `sessions/thread_david.md` mtime
(2026-09-09 09:47:23 -07:00) is also unchanged and, on inspection, was **never** touched by T5 or
T6 either — `write_thread` requires a `<<<TTROS_THREAD...TTROS_THREAD>>>` delimiter block in the
response, which plain `-z` oneshot answers never contain, so `write_thread` was not a live channel
for any of these turns regardless of this step's gate (a correction to this step's own Part B
framing: the gate's `append_session_turn` half is what actually mattered in practice).

Re-ran `assemble()` fresh (same query) and `search_history` with a phrase unique to D1's new
answer ("Do not start with the MLS dashboard"): the phrase appears in neither — confirming both
new turns are ineligible for recency selection and unfindable by search, exactly as designed.

---

## VERDICT

**Part B (test-turn isolation): PASS, live-confirmed both directions.** The write-gate mechanism
works exactly as designed — zero vault writes from two live marked turns, confirmed by direct
file mtime/line-count inspection, not inference. D1's forbidden-claim criterion (GVR board
count, Fraser Valley cities) also passed live, though incidentally: the specific old residue that
caused T6's D1 failure has aged out of the top-2 recency selection for this exact query wording,
not because this step removed it (it is still on disk, unrepaired, per this step's own
authorization boundary — see the residue plan above). A differently-worded query could still
surface it; D2's own trace shows the underlying 2026-09-09/T6 residue is still fully reachable by
`search_history` today.

**Part C (bounded missing-fact retrieval): diagnosed, not fixed — correctly, per instruction.**
The passage route (`search_calls`/`open_call`) is architecturally scoped to
`sources/historical_calls/` only and cannot reach `sources/intake/records/`, so no authorized
smallest-fix existed for this step to apply. D2 reproduced the same over-retrieval pattern T6
found, for the same reason, with correct provenance and a correct answer.

**What this licenses:** a real, verified, working mechanism that stops *future* David test turns
from contaminating the vault (thread and journal both), proven live in both directions. Existing
residue from T5/T6/earlier manual research remains on disk and unrepaired (by design — no
authorization to touch it), so any question worded similarly to those old turns can still surface
them via recency or `search_history`. The missing-fact retrieval ceiling (`api_calls ≤ 4`) remains
unmet whenever the fact lives outside `sources/historical_calls/`, which includes every
semantically-ingested source — this is now precisely diagnosed (broken passage-tool scope, plus a
spillover-recovery message naming a tool David doesn't have) but requires a brain-MCP or Hermes
behavior change outside this step's authorized surface.

**What this does not license:** treating either D1 or D2 as a clean PASS on call-count grounds —
both exceeded their ceilings, for named, pre-existing, undiagnosed-by-this-step-alone-but-not-
fixable-in-scope reasons. Not a basis for declaring the over-retrieval problem closed, and not a
basis for scoring B7 today (contamination is reduced, not eliminated, for differently-worded
questions).
