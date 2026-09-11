# STEP T4 — close out T3 mechanically before the one live Fred question. ZERO MODEL CALLS.

Full predictions, evidence and command output: `scripts/stepT4_post_t3_closeout.transcript.txt`
(tee'd, this file refuses to overwrite). **Model calls: 0 / declared max 0**, confirmed throughout
— every measurement in this task is either a real file read, a real zero-model offline instrument
(`hermes prompt-size --json`, direct `discover_mcp_tools`/`registry.get_definitions`/
`context_assembler.assemble()`/`.render()` calls), or a real, non-dispatching CLI subcommand.

---

## ITEM 0 — T3 backup check

**No dedicated pre-T3 preimage exists** under `/home/liam/ttros_backups/`. The one config.yaml
preimage found there (`david_config.yaml.PREIMAGE_20260908T044915Z`) is STEP U's pre-upgrade
snapshot from 2026-09-08 — a different purpose, predating T3, missing keys added between STEP U
and T3. T3's own session copied config.yaml to a `/tmp` scratchpad path before editing — ephemeral,
not under `ttros_backups/`. **Recorded as a genuine T3 method gap** against permission-header rule
6. T3's documented hand-edit rollback (reverse the exact `disabled_toolsets` lines in its own
transcript) stands as the only real rollback path for the pre-T3 state.

Immutable preimage of the **current** (post-T3) live config.yaml taken before Item 1:
`/home/liam/ttros_backups/stepT4_2026-09-10/david_config.yaml.PREIMAGE_pre-item1_20260910`
(sha256 `7b2ca866...0274`, chmod 444).

---

## ITEM 1 — Queue-MCP contradiction

**Prediction (obsolete residue, no live path needs a David-side queue tool) confirmed true.**
Traced end to end: David's execution handoff is a JSON block inside his ordinary text reply
(`rules/david_execution_handoff.md`), parsed downstream by `dashboard/backend/main.py:4635-4658
_david_execution_handoff()` (pure string/regex parsing) and turned into a queue item by
`main.py:7777 _hermes_objective_from_handoff()` — a plain backend Python function, zero David tool
calls anywhere in the chain. `connectors/telegram_bridge/` is protected and unread, but the
contract itself is surface-agnostic (specifies what David emits, not how a bridge consumes it), so
the conclusion holds architecturally regardless of surface.

**Read-only survey:** grepped every profile's `config.yaml` under `~/.hermes/profiles/*/` — **only
`david` registers a `queue` MCP server.** No other profile, including `aos-orchestrator` (the real
execution profile, checked directly), references it. No candidate production defect elsewhere.

**Applied:** removed the `queue:` entry from `~/.hermes/profiles/david/config.yaml`'s
`mcp_servers:` block. Exact change/rollback recorded in the transcript.

**Wall-time, 3 runs each, fresh process, real numbers (prediction of ~3-4s was too low — real
attempts pay subprocess-spawn/import time, not just backoff sleep):**

| Run | Before (queue present, failing) | After (queue removed) |
|---|---:|---:|
| 1 | 7.840 s | 1.481 s |
| 2 | 8.386 s | 1.490 s |
| 3 | 10.164 s | 1.467 s |

`brain` unaffected in every run: still 10 tools / 4,526 B, confirmed directly. Queue's connect
failure is gone (no error output post-removal).

---

## ITEM 2 — Persistence of David's five-tool scope

**Prediction confirmed on all counts.** Nothing in the repo writes `agent.disabled_toolsets` or
`mcp_servers.queue`: `tools/install_hermes_context_assembler.py` (the only repo script that
touches david's config.yaml at all) is additive/idempotent — manages a plugin symlink, calls native
`hermes plugins enable`/`hermes mcp add`, checks (never writes) memory keys, never references
either key; re-running it today is a no-op against both. Surface searched: `grep -rln config.yaml
--include=*.py` across the whole repo (2 other hits, both read-only or non-reading). Hermes'
own `hermes_cli/config_migrations.py` (641 lines, read in full): zero references to either key in
any migration step — migrations are additive/table-driven ("a step may only persist values that
differ from the schema default"), so an in-place version bump cannot touch them. No systemd user
unit references profile regeneration (`grep -l profile ~/.config/systemd/user/*.service` → zero
hits). **Realistic loss path, as predicted: a manual `hermes setup`/profile re-create, not any
repo or systemd surface.**

**Outcome — nothing owns it, so an immutable final-state snapshot was saved:**
`/home/liam/ttros_backups/stepT4_2026-09-10/david_config.yaml.FINAL_postT4item1_20260910`
(sha256 `7bb26334...9650d`, chmod 444).

**Exact one-block re-apply instruction**, if this file is ever lost or regenerated — add under
`agent:` in `~/.hermes/profiles/david/config.yaml`:
```yaml
agent:
  max_turns: 150
  disabled_toolsets:
    - browser
    - web
    - vision
    - tts
    - file
    - skills
    - terminal
    - code_execution
    - delegation
```
and remove any `mcp_servers.queue` entry if `tools/queue_mcp.py` is still absent.

**Offline assertion to confirm re-apply worked** (zero model calls):
```
hermes -p david prompt-size --json
```
→ `tools.count == 5` and, per the tool-array assertion script used in this task, the resolved
names equal exactly `{memory, clarify, tool_search, tool_call, tool_describe}`.

---

## ITEM 3 — Return the suite to green — NOT DONE, and why

**Prediction half-confirmed, half more serious than predicted.** Working tree mode: `-rw-r--r--`
(644, no exec bit). Git-index mode: also `100644` — but `git config core.fileMode` is **`false`**,
meaning git has never tracked this repo's real executable bits at all; "restore the mode git
records" is not a meaningful instruction here, since git's record was never authoritative.

**The test's invocation is correct, not a test bug:** `tests/test_hermes_context_plugin.py:109`
calls `_pre_llm_call()`, which reaches `hooks/hermes_context_assembler_plugin/__init__.py:32-40
_invoke()`, which runs `subprocess.run([str(HOOK)], ...)` — a bare path, no interpreter, requiring
the +x bit. This is **the exact same code path production uses**: `register()` in the same file
wires this into Hermes' native `pre_llm_call`/`post_llm_call` plugin hooks, and the
`plugins/ttros-context-assembler` symlink under **all 8** scoped profiles resolves to this same
repo file — there is no separate "installed copy" to compare against; the repo file *is* the
production artifact.

**Worse: 7 of 8 profiles (every one except david) also configure a shell-hook fallback** that
names the same broken file directly as a command (`hooks.pre_llm_call`/`post_llm_call:
[{command: .../hooks/context_assembler_hook.py}]`) — identically affected. David alone has no
fallback at all.

**Nightly-backup cross-check, read-only:** every backup from 2026-08-04 through
2026-09-10T01:00:00Z (this morning) shows this exact file at `755`, including the most recent one
taken *after* yesterday's content edit (same byte size as the current live copy). `755` is the
long-standing, correct, production mode; the bit was dropped sometime between 1 AM today and this
session. The comparable, currently-working hook `hooks/b7_test_material_guard.py` is `755` right
now, confirming this is the normal pattern for every other hook in this repo.

**Per this item's own explicit decision rule — "If the installed production copy is affected,
report it prominently and do NOT change the installed copy in this step" — NO chmod was applied.**
The installed production copy is confirmed affected (it is the same file), so the fix is
deliberately withheld here as a runtime change reserved for Liam.

**Severity, reasoned from already-established facts:** STEP U's own prior audit established that
Hermes' plugin-hook call sites swallow exceptions (`except Exception: pass`), so this
`PermissionError` would be silently absorbed on every real turn across all 8 profiles — but the
same STEP U fail-closed `RuntimeError` gate should then see the mandatory context marker absent and
block the model call outright (the safe failure mode). Corroborated, not just theorized: this
session confirmed `test_installed_native_turn_guard_rejects_missing_registered_context` and its
sibling still pass (2 passed).

**Suite (unchanged from T3, since no fix was applied), run per header rule 8:**
```
PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest -q
```
→ **828 passed, 1 failed** (same test, same cause), **223 subtests passed**, 829 collected.
`git diff --check`: exit 2, the same two known pre-existing whitespace findings, no new ones.
**Not 829/829** — the expected fix is explicitly blocked by this item's own decision rule now that
the production coupling is proven, not by any remaining technical obstacle.

---

## ITEM 4 — Correction to T3's eager-MCP arithmetic

Appended as a dated correction section at the end of `scripts/stepT3_david_tool_scoping.md`
(original text untouched; the corrected sentence now points to it). Summary:

- **(a)** T3's break-even claim was arithmetically wrong at N=2 residual round trips (benefit
  57,768 tokens clearly exceeds the 29,400-token fixed tax there — eager would win, not the tax).
- **(b)** T3 priced eager gross (+4,526 B). Netted against the bridge triad it replaces (2,551 B,
  live-measured) and measured on a **copy** of david's profile (never the live one): net cost is
  **+1,975 B** (all 10 tools) or **+889 B** (6 TTROS tools, protocol tools excluded via the native,
  already-live-on-operator-lean `mcp_servers.<name>.tools: {resources: false, prompts: false}`
  key — verified empirically on the copy, not just read from source). **Never negative** — this
  task's own prediction ("negative if protocol tools excludable") was wrong in sign.
  A genuine, disclosed `hermes prompt-size` instrument anomaly specific to `tool_search.enabled:
  "off"` (two unrelated native tools appear; isolated to that literal value, not fully
  root-caused) meant the net figure was built by combining two direct, un-confounded
  measurements instead of trusting prompt-size's own "off" output.
- **(c)** The 28,884-tokens/round-trip figure is stale post-T3; re-estimated (ESTIMATE only) at
  ~11,674 tokens/round-trip from the smaller post-T3 prefix. This *tightens* the case for staying
  lazy — real post-T3 break-even needs close to 3 residual round trips, not 1.
- **(d)** Read-only coupling check: B6's own investigation instrument already keys on resolved
  `mcp__brain__*` names (not the `tool_call` wrapper), the B7 guard's blocklist has no overlap, and
  the fail-closed marker-check is independent of eager/lazy — **no coupling risk found.**

**No change applied to the live profile for Item 4** (explicitly forbidden by the item). Revised
recommendation: still leave `"auto"` — corrected arithmetic narrows the margin materially but does
not flip the decision; Liam decides.

---

## ITEM 5 — Surface and context-file reconciliation

**Prediction partly wrong, corrected on measurement.** The ~3,773 B tier is **not** AGENTS.md or
CLAUDE.md content — it is `.hermes.md` (TTROS's own generated canonical map,
`scripts/step5_map_generator.py`), which wins outright under Hermes' own "first found wins:
.hermes.md/HERMES.md (walk to git root) → ..." rule (`agent/prompt_builder.py:1578`). The literal
string "CLAUDE.md" found in the tier is one line of Hermes' own small workspace-snapshot metadata
block (git status / recent commit subjects / verify command / "Context files: AGENTS.md,
CLAUDE.md" — names only, not content) — **no coding-agent instruction file content leaks into
David's prompt.** The workspace-snapshot metadata itself (git status, commit subjects) is real,
disclosed, coding-agent-shaped scaffolding irrelevant to David's role — named, not fixed.

`.hermes.md`'s walk-to-git-root discovery is **cwd-insensitive within the repo**: `aos-backend
.service`'s own `WorkingDirectory` is `/home/liam/agentic-os-live/dashboard` (confirmed via
`systemctl --user show`), not the repo root — but the walk-up logic and git's own repo-root-relative
commands mean the dashboard surface loads the identical content anyway. The Telegram gateway's
actual cwd is **unproven** (`connectors/telegram_bridge/` is protected, unread this session);
`.hermes.md`'s own discovery rule stops at the exact cwd with no git-root ancestor, so this
genuinely could differ there — named as unproven, not assumed either way.

**`agent.disabled_toolsets` under platform-toolset resolution, proven via the same offline
instrument:** `_build_inspection_agent("cli")` and `_build_inspection_agent("telegram")` against
david's real profile both resolve to the **identical** 5 tools. Proven at the config/toolset-
resolution layer; **not** an end-to-end proof of the real, protected Telegram bridge process
itself, which was not and could not be read this session.

---

## ITEM 6 — Final constructed Fred/MLS request

Surface: CLI-David. cwd: `/home/liam/agentic-os-live` (repo root).

| | Bytes |
|---|---:|
| Tools | 7,493 |
| System prompt, WITH the item-5 context tier | 21,725 |
| System prompt, WITHOUT the item-5 context tier | 17,952 |
| Assembled context + question (`render()`, fresh) | 43,422 |
| **Total, WITH tier** | **72,640** |
| **Total, WITHOUT tier** | **68,867** |
| vs. T3's 72,640 B | **+0 B** (expected — items 1-3 touched neither tools, instructions, nor context-assembly bytes) |
| vs. T1's 110,886 B | **−38,246 B / −34.5%** (with tier) or **−42,019 B / −37.9%** (without) |

**Tool-array assertions, both directions rehearsed as failing this time** (T3 only rehearsed
PRESENT): asserting a nonexistent tool present → correctly FAILED; **asserting a real KEEP tool
(`memory`) absent → correctly FAILED**, proving the ABSENT-direction checker is not a rubber stamp
either. Both real assertions (PRESENT for the 5 KEEP tools, ABSENT for a REMOVE sample) PASS.

**T1's six `assemble()` cases, re-run: byte-identical to T1/T2/T3** — Fred/MLS 4,966 B (2 cards),
CCI 7,262 B (3 cards), Andrea 4,651 B (2 cards), both negative controls and the fallback control
192 B / no cards. No regression; expected, since nothing in `context_assembler.py` was touched.

---

## CLOSEOUT

**What each item established, plain English:**

- **Item 0:** T3 left no proper backup-dir preimage — a real gap, now closed for this session's
  own changes going forward.
- **Item 1:** the orphaned `queue` MCP registration was genuinely dead weight — removed from
  David's live config only, saving ~6-9 seconds of session-start wall time, with `brain` and every
  other profile unaffected.
- **Item 2:** David's five-tool scope has no repo or Hermes-migration owner, but nothing threatens
  to silently regenerate it either — a snapshot and a one-block re-apply recipe now exist.
- **Item 3:** a real, currently-live production defect was found — `hooks/context_assembler_hook.py`
  lost its executable bit sometime this morning, breaking the actual context-assembly hook for
  **all 8** scoped profiles, not just a test. Per this item's own rule, it was **not** fixed here —
  it is reported prominently for Liam to fix as a runtime change. The safety net (STEP U's
  fail-closed guard) is confirmed still intact, so the likely live effect is calls being blocked
  outright rather than silently degraded, but this should be treated as urgent.
- **Item 4:** T3's eager-MCP math had two real errors (a wrong break-even comparison, and an
  unnetted gross cost); corrected, the net cost of going eager is a small but real permanent tax
  (+889 B to +1,975 B), never negative. No live change made.
- **Item 5:** the "mystery" 3.7 KB tier is TTROS's own canonical map, not contamination from
  another agent's instructions — a smaller, real finding (git-status scaffolding) survives, named
  not fixed. David's tool scope is proven identical under CLI and Telegram platform resolution at
  the config layer; the real Telegram bridge itself remains unproven (protected).
- **Item 6:** the final Fred request is unchanged from T3 (72,640 B, since none of items 1-3
  touched the measured components) and remains ~34-38% below T1's original 110,886 B. Both
  tool-array assertion directions are now proven capable of failing.

**What changed live, exact files:**
`~/.hermes/profiles/david/config.yaml` — the `queue:` mcp_servers entry removed (Item 1 only).
Nothing else on any profile was touched. `scripts/stepT3_david_tool_scoping.md` — a dated
correction section appended (original text untouched).

**Preimages:** `/home/liam/ttros_backups/stepT4_2026-09-10/` — pre-item-1 preimage, post-item-1
final snapshot, and the item-4 what-if copy (never applied live).

**Suite:** 828 passed / 1 failed / 829 collected — unchanged from T3, because the one failure's
fix is deliberately withheld per Item 3's own rule pending Liam's decision on the live permission
bit. `git diff --check`: the same two known pre-existing findings only.

**Model calls: 0.**

**What this licenses:** the one live Fred question named in T3
(`hermes -p david -z "What happened in my meeting with Fred, and what did he say about MLS?"`) may
proceed on the CLI-David surface, cwd `/home/liam/agentic-os-live` — **once Liam has separately
decided what to do about the Item 3 permission-bit finding**, since that bit currently gates
whether the mandatory context marker can be injected at all on every profile including david.

**What this does NOT license:** any `tools.tool_search.enabled` change on the live profile (Item
4's corrected arithmetic still doesn't clear the bar, and this task explicitly forbade applying
it); B7; any change to a profile other than david; a chmod on `hooks/context_assembler_hook.py`
(explicitly reserved for Liam per Item 3's own decision rule); a commit or push.

No commit. No push.
