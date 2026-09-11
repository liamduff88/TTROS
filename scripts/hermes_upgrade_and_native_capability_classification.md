# STEP U — Hermes in-place upgrade, breakage repair, and native-capability classification

Unnumbered step, outside the rev11 sequence. rev11 stays closed. Evidence directory (outside
the repo, per "no other new files"): `/home/liam/ttros_backups/hermes_upgrade_20260908/`.

## Result in plain English

Hermes went from v0.18.0 (2026.7.1) to **v0.21.1 (2026.9.7)**, the latest tagged stable release,
via the official `hermes update` path. The upgrade's own stash/reapply step silently dropped a
pre-existing, load-bearing local patch to Hermes' native `agent/turn_context.py` — the fail-closed
guard that blocks any model call for the seven TTROS profiles when the assembler's context marker
is absent. I checked the upgraded version for a native, non-patch way to restore that guarantee
(plugin hooks, shell hooks, config keys) and found none: **every plugin hook call site in
`agent/turn_context.py` / `agent/turn_api_request.py` swallows exceptions from hooks
(`except Exception: pass` / `logger.warning(...)`), and the native shell-hook blocking mechanism
is hardcoded to only honor blocking on `pre_tool_call`, never on `pre_llm_call`/`pre_api_request`.**
With no native equivalent available, I reapplied the minimum patch needed to restore the exact
pre-upgrade behavior (same two edits: the profile-scoped `RuntimeError` gate, and the spill-skip
for the TTROS marker), verified against the upgraded code. `tools/validate_unbound_runtime.py
--status` went 44/44 → 3 failing → 44/44 again.

The upgrade also broke two TTROS-owned MCP server scripts (`mcp` SDK 1.26.0 → 2.0.0 renamed
`mcp.server.fastmcp.FastMCP` to `mcp.server.mcpserver.MCPServer`, no compat shim) — fixed, same
two-line pattern in both files. A full repo test-suite run (beyond STEP U's required checks, run
as extra diligence) caught a third, more serious regression: Hermes v0.21.1's new tool-search
virtualization (`tools.tool_search`, default `"auto"`) collapsed every tool the **operator-lean**
profile exposes into 3 generic bridge tools, breaking `operator_lean_oneshot.py`'s own fail-closed
exact-tool-set check on every real invocation — this profile was completely non-functional
post-upgrade until fixed (see Phase 4). Both required Phase-4 repairs (B7 guard tool-list
re-derivation; `memory.write_approval: true`) are done and verified with a rehearsed failing case. Post-upgrade
smoke result (7/7) equals the pre-upgrade baseline (7/7). No commit, no push, no B7 pass, no vault
edit, no second Hermes install.

## Predictions (written before Phase 2 ran; full text in `predictions.txt`)

| # | Prediction | Outcome |
|---|---|---|
| a | 7/7 pre-upgrade smoke checks pass | **Correct** — 7/7 |
| b | Both `pre_llm_call`/`post_llm_call` and `pre_api_request`/`post_api_request` hook APIs coexist pre-upgrade; `pre_llm_call` survives the upgrade | **Correct both ways** — confirmed via grep pre- and post-upgrade |
| c | `memory.write_approval` not currently set | **Correct** — absent from config.yaml |
| d | `BLOCKED_TOOL_NAMES` does not cover every file-reading-capable tool | **Correct** — `terminal`/`process` (renamed `process_manage` in v0.21.1) were enabled for David and absent from the list |
| e | `context_file_max_chars` still exists, value 40000 | **Correct**, unchanged by the upgrade |

## Phase 1 — Preserve (evidence in `/home/liam/ttros_backups/hermes_upgrade_20260908/`)

- Install method determined read-only **before** touching anything: git checkout at
  `/home/liam/.hermes/hermes-agent` (remote `NousResearch/hermes-agent`), venv at
  `hermes-agent/venv`, invoked via the `/home/liam/.local/bin/hermes` wrapper. Not pip/pipx/npm.
- `state.db.PREIMAGE_20260908` — David's `state.db` copied out of `~/.hermes` before any upgrade
  action. `state.db.source.sha256` == `state.db.copy.sha256`
  (`0b51150223ec00f51d5fff00265426abc17333cef634c896291b38a42e17f1e8`), asserted equal in-script.
- `david_profile_snapshot_20260908.tar.gz` — full David profile directory, sha256 recorded.
- `unrelated_profiles.sha256` — sha256 of `config.yaml` for aos-delivery/aos-marketing/aos-ops/
  aos-orchestrator/aos-revenue, taken before the upgrade.
- `guard_hooks.sha256` — sha256 of `hooks/b7_test_material_guard.py` and `hooks/runtime_guard.py`
  before any edits.
- Fixed a stale `.git/shallow.lock` in the hermes-agent checkout (dated Jul 31, over a month old,
  no process holding it — confirmed via `ps aux` before removal) that was blocking every fetch,
  including the one this step needed. A lock-file artifact, not data; no backup was needed or taken.

## Phase 2 — Pre-upgrade smoke test (`smoke_test.py`, `pre_smoke.txt`/`.json`)

Declared model-call budget: 4 (hard-stopped in-script). Actual: 2 (checks 1 and 6 only; checks
2/3/4/5/7 make zero model calls by design/verified). Result: **7/7 passed.**

| # | Check | Result | Note |
|---|---|---|---|
| 1 | David answers a trivial CLI prompt | PASS | `hermes -p david -z "..."` → "PONG" |
| 2 | Context assembly produces context; total size recorded | PASS | 37,060 bytes / 8,223 tokens, 15 blocks, `write_artifact=False` (no queue side effect) |
| 3 | `session_search` returns results; raw vs. summarized | PASS | See below — settled definitively |
| 4 | Memory config (enabled / write_approval / background review) | PASS (report only) | `memory_enabled: true`, `write_approval` absent, `background_review.enabled` defaults `true` (not overridden) |
| 5 | Step 6 depth tools reachable | PASS | `search_calls`/`open_call`/`open_note`/`search_history` all callable |
| 6 | David→Hermes execution handoff completes a trivial task | PASS | terminal tool ran `echo HANDOFF_OK`, echoed back |
| 7 | Dashboard/backend responds | PASS | `aos-backend.service` (uvicorn, port 8010 per `systemctl --user`), `/api/health` → 200 |

**Check 3 settled definitively, with a real negative case found and explained.** Official docs
("raw, no summarization") are correct for v0.18.0: `tools/session_search_tool.py`'s own docstring
and code confirm zero LLM calls in any of its three modes — it is pure SQLite FTS5 + message rows.
But a literal query for "TTROS" via `profile='david'` (the cross-profile path) genuinely returned
zero results on the first attempt, not because the tool is broken, but because
`session_search(profile=...)` internally opens the target `state.db` via
`SessionDB(..., read_only=True)`, and `SessionDB._fts_enabled` is only ever set `True` on the
read-write schema-migration code path — a read-only open silently leaves FTS disabled and every
query returns `count: 0`, indistinguishable from "no matches." Reproduced directly:
`fts_enabled: False` read-only vs. `fts_enabled: True` read-write, same DB, same query, 0 vs. 3
results. **Recorded as a finding, not acted on** — it is upstream `hermes_state.py`/
`session_search_tool.py`, not a TTROS component, and out of STEP U's authorized surface. The smoke
check itself was corrected to open the DB the way David's own live session actually does
(read-write), which is what should be graded.

## Phase 3 — Upgrade

- Live-checked: installed v0.18.0 (git HEAD `05cbddc01234ea120cccc1f62d36f1ef352b0d52`, describe
  `v2026.7.1-8089-g05cbddc01`) vs. upstream. Latest tagged stable release: **v2026.9.7 (hermes-agent
  0.21.1)**, tagged 2026-09-07; `origin/main` was one small CLI fix commit ahead of that tag.
- Exact rollback command recorded in `rollback_command.txt` **before** the upgrade ran (git reset
  to the recorded pre-upgrade SHA, venv re-sync, profile restore from the Phase 1 snapshot,
  service restart) — required by the step, not needed in the end.
- Ran `hermes update --backup --yes` (the tool's own official upgrade path: git fetch, reset to
  origin/main, `uv pip install -e '.[all]'`). Hermes' own pre-update backup:
  `/home/liam/.hermes/backups/pre-update-2026-09-08-122646.zip` (180.9 MB).
- Result: v0.18.0 → **v0.21.1 (2026.9.7)**, upstream `b2aa855b`. Full transcript:
  `phase3_upgrade_transcript.txt`.
- No restart of TTROS-managed services was needed: `aos-backend.service` and `aos-runner.service`
  both run under `dashboard/backend/.venv`, entirely independent of the hermes-agent venv, and
  every `hermes` invocation from either is a fresh subprocess that already picks up the upgraded
  code — confirmed via `systemctl --user cat`, not assumed.

## Phase 4 — Repair

### The dropped native-source patch (stop-and-ask, resolved in-session per follow-up authorization)

The update's auto-stash-and-reapply hit a merge conflict on `agent/turn_context.py` and left the
working tree at the clean post-upgrade state **without** reapplying the stashed local diff (stash
preserved at `157e38ce196283d9a3e1396d9b484ed12f5664f2`, nothing lost). That diff was not
incidental: it is the fail-closed gate `tools/validate_unbound_runtime.py` and
`tests/test_hermes_context_plugin.py`/`tests/test_unbound_runtime_drift.py` treat as a Step 0–3
invariant — `RuntimeError("TTROS model call blocked: mandatory assembled context is absent")` for
all seven TTROS profiles when the assembler didn't supply `TTROS_ASSEMBLED_CONTEXT_V1`, plus a
spill-skip so that marker is never replaced by an unreadable disk pointer. Confirmed mechanically:
`validate_unbound_runtime.py --status` dropped from 44/44 to exactly 3 failing
(`native_marker_required`, `assembled_context_not_spilled`, `seven_profiles_scoped`) — everything
else survived the upgrade clean.

**Searched for a native replacement before touching source, per the follow-up instruction:**

- Python plugin hooks (`pre_llm_call`, `pre_api_request`) — both call sites
  (`agent/turn_context.py::_collect_pre_llm_call_context`,
  `agent/turn_api_request.py::_fire_pre_api_request_hook`) wrap the hook invocation in a bare
  `except Exception` that logs and continues. A hook plugin cannot abort a turn by raising in
  either version — confirmed unchanged pre- and post-upgrade by reading both.
- Native shell hooks (`hermes hooks`, `agent/shell_hooks.py`) — do support a `block` directive
  (exit code 2 or `{"action":"block"}` JSON, with a `fail_closed` option), but
  `_BLOCKING_EVENTS = frozenset({"pre_tool_call"})` is hardcoded: blocking is only honored on
  `pre_tool_call`. Config explicitly warns `fail_closed=true` on any other event "will be ignored
  at runtime." There is no event that fires before the LLM/API call and supports blocking.
- Conclusion: **no native mechanism exists in v0.21.1** to abort a turn pre-API-call based on
  missing context. Reapplying the minimum patch was therefore necessary, not a default choice.

**What was reapplied** (verbatim two-part diff, nothing added or redesigned): in
`agent/turn_context.py`, (1) inside `_collect_pre_llm_call_context`, the disk-spill call is
skipped when the hook's own context piece contains `TTROS_ASSEMBLED_CONTEXT_V1`; (2) immediately
after `plugin_user_context = _collect_pre_llm_call_context(...)` in `build_turn_context`, the
profile-scoped `RuntimeError` gate. Upstream had refactored the old monolithic inline code into
these two separate functions between v0.18.0 and v0.21.1 (hence the merge conflict), so the patch
was re-applied by hand at the equivalent new location rather than force-applying the stale stash
diff. `import os` added (not previously imported in this file).

**Verification:**
- `python3 -c "import ast; ast.parse(...)"` — syntax OK.
- `tests/test_hermes_context_plugin.py` + `tests/test_unbound_runtime_drift.py` — 12/12 passed,
  including the existing positive (`test_installed_native_turn_guard_rejects_missing_registered_context`)
  and negative (`test_unregistered_profile_receives_no_context`,
  `test_david_assembles_without_disabling_native_personal_memory_or_using_step6`) cases — the
  detector already had both directions built in.
- `validate_unbound_runtime.py --status`: **44/44 passing**, back to the pre-upgrade baseline.
- Live post-upgrade smoke re-run (below) exercised the real `hermes -p david -z` path end to end
  through the patched code, not just unit tests.

**Classification: UPSTREAM-PATCH.** No native equivalent exists in v0.21.1. Necessary, minimal,
unchanged in scope from the pre-upgrade version. Revisit if a future Hermes release adds a
blocking pre-LLM/pre-API hook event — recheck this file first if so.

### Two TTROS-owned MCP servers broken by the `mcp` SDK bump (found via post-upgrade smoke re-run)

The upgrade moved `mcp` 1.26.0 → 2.0.0 (and added `mcp-types` 2.0.0). `mcp.server.fastmcp.FastMCP`
no longer exists in 2.0.0, no compat shim — replaced by `mcp.server.mcpserver.MCPServer`, confirmed
API-compatible for the calls TTROS makes (`MCPServer(name)`, `.tool()`, `.run(transport="stdio")`).
Fixed in both TTROS-owned MCP server scripts (two-line change each, import + constructor only):
- `tools/brain_memory_mcp.py` (David's `brain` MCP server — `search_calls`/`open_call`/`open_note`/
  `search_history`/`remember_brain_knowledge`/`brain_memory_status`)
- `tools/operator_lean_mcp.py` (the `operator-lean` profile's queue/kanban tool server)

Verified both import cleanly under the hermes-agent venv post-fix; post-upgrade smoke check 5
(depth tools reachable) went FAIL → PASS. `tools/queue_mcp.py` (referenced by David's
`mcp_servers.queue` in config.yaml) does not exist on disk — **pre-existing**, already shown
deleted in git status before this session started, unrelated to the Hermes upgrade. Recorded, not
touched (out of STEP U's scope; not upgrade breakage).

### `operator-lean` completely broken by new tool-search virtualization (found via full-suite run)

A full repo test-suite run beyond STEP U's required checks caught
`tests/test_telegram_conversational_routing.py::test_live_loaded_operator_preamble_has_exact_bounded_tools_under_budget`
failing: the live tool preamble for `operator-lean` came back as `{'tool_call', 'tool_search',
'tool_describe'}` instead of the 9 expected `mcp__operator__*`/`mcp__brain__*` names.

Root cause, confirmed by reading `hermes_cli/config_defaults.py`: v0.21.1 adds **tool-search
virtualization** — `tools.tool_search.enabled` defaults to `"auto"`, which replaces every
deferrable (MCP/non-core-plugin) tool in the model-facing array with generic `tool_search`/
`tool_describe`/`tool_call` bridge tools once at least one such tool exists (a context-budget
feature; native, built-in "core" toolsets like `terminal`/file tools/`memory`/`browser_*` are
never deferred and were unaffected — this is why David's own tool set, and the B7 guard's
name-based blocking of core tools, were not impacted). Operator-lean's entire exposed surface is
MCP (`operator` + `brain` servers; its only core toolset is `kanban`), so `"auto"` collapsed it
completely. This is not merely a test failure: `tools/operator_lean_oneshot.py` runs the identical
`EXPECTED_TOOLS` check live on every real invocation and raises `RuntimeError` on a mismatch — the
profile was fully non-functional (fails closed, at least, rather than silently) from the moment of
upgrade until this fix.

Fix: added `tools: {tool_search: {enabled: "off"}}` to
`~/.hermes/profiles/operator-lean/config.yaml`, restoring eager/direct listing of all 9 named
tools — verified live via `operator_lean_oneshot.py --inspect-preamble` (9/9 exact names) and via
the now-passing test. This is a profile-config change, not a source patch — squarely within Phase
4's "repair of upgrade breakage in TTROS's own... profile config" authorization, and does not
touch any of the five profiles the PROOF checklist requires to stay hash-identical (operator-lean
is not one of them; re-verified those five unchanged after this edit).

While in this codepath, also fixed a second, imminent break in the same file:
`tools/operator_lean_oneshot.py:38` imported `discover_mcp_tools` from the deprecated
`tools.mcp_tool` compat-shim path (Hermes' own deprecation notice: "kept only for external
plugins... removed on 2026-09-14" — six days from this session). Updated to the new
`tools.mcp_tool_discovery` path (same function signature, confirmed); the deprecation warning is
gone and the preamble inspection still returns the exact 9 tools.

### Required repair 1 — B7 guard tool-list re-derivation (`hooks/b7_test_material_guard.py`)

Re-checked `BLOCKED_TOOL_NAMES` against David's current tool registry (`hermes -p david tools
list`, post-upgrade). Confirmed via direct rehearsal — **the detector was made to fail before it
was trusted to pass**:

```
BEFORE fix, TTROS_BRAIN_ROOT set (simulated active B7 run):
  terminal   + tool_input {"command": "cat scripts/step3_b7_harness.py"}  -> {}            (NOT blocked)
  process_manage + {"action": "list"}                                     -> {}            (NOT blocked)
AFTER fix, same inputs:
  terminal                                                                -> blocked
  process_manage                                                          -> blocked
  mcp__brain__search_calls / mcp__brain__open_note (control)              -> {}  (still permitted)
  terminal, TTROS_BRAIN_ROOT unset (guard inert outside a B7 run)         -> {}  (unaffected, by design)
```

Root cause: David's `terminal` toolset (tools `terminal` and, as of v0.21.1, `process_manage` —
renamed from `process`) can run an arbitrary shell command, including `cat` on any of the same
paths `read_file`/`search_files` were blocked for reaching, and neither name was in
`BLOCKED_TOOL_NAMES`. The defense-in-depth path regex does **not** independently catch this: it
anchors on the path substring appearing at the start of a value or right after `/`
(`(?:^|/)scripts(?:/|$)`), which a shell command string breaks — `"cat scripts/..."` has `scripts`
preceded by a space, not `/` or start-of-string, so the regex does not match. The name-based block
is the only effective layer for this vector. Fixed:
`BLOCKED_TOOL_NAMES = {"search_files", "read_file", "execute_code", "session_search", "terminal",
"process_manage"}`. Existing suite: `tests/test_b7_test_material_guard.py` — 15 passed / 21
subtests passed, unchanged.

### Required repair 2 — `memory.write_approval: true`

Added to `~/.hermes/profiles/david/config.yaml` under the existing `memory:` block. Confirmed live
via `tools.write_approval.write_approval_enabled(MEMORY)` → `True` under David's `HERMES_HOME`.
Background review (`auxiliary.background_review.enabled`, default `true`, not overridden by David)
keeps running — this key does not stop it — but its writes (and any foreground memory write) now
stage under `pending/memory/` for out-of-band review instead of committing directly, closing the
"unreviewed writes into always-on context" gap the step named.

## Post-upgrade smoke re-run (`post_smoke.txt`/`.json`)

Declared max 4, actual 2 model calls (checks 1/6). **7/7 passed — equals the pre-upgrade
baseline**, after the two TTROS MCP-server fixes above (first post-upgrade run was 6/7, check 5
failing on the `mcp.server.fastmcp` import; second run, after the fix, 7/7).

## Phase 5 — Classification (KEEP / RELAX / REMOVE / TTROS-SPECIFIC)

| Component | Classification | Native capability (if REMOVE/RELAX) / basis |
|---|---|---|
| `search_history` (`tools/brain_memory_mcp.py`) | **TTROS-SPECIFIC — keep** | Checked against native `session_search` first, as directed: **different corpora, not a deletion candidate.** `session_search` (`tools/session_search_tool.py`) indexes Hermes's own conversation/message SQLite store only. `search_history` full-text-searches the Business Brain **vault** (markdown knowledge notes) via `aos_indexer`/repo-wide FTS. Zero overlap; native `session_search` has no access to vault content at all. |
| `search_calls`, `open_call`, `open_note` (`tools/brain_memory_mcp.py`) | **TTROS-SPECIFIC — keep** | As expected going in: historical-call transcripts and arbitrary vault notes, vault-scoped by `tools/brain_memory.py::_target`. No native equivalent (native memory/session tools don't reach the vault). |
| `remember_brain_knowledge` / `brain_memory_status` | **TTROS-SPECIFIC — keep** | Business Brain write/status semantics (knowledge-state taxonomy, commitment-language gate) have no native counterpart. |
| `agent/turn_context.py` fail-closed patch | **UPSTREAM-PATCH — necessary, reapplied** | No native blocking hook fires before an LLM/API call (see Phase 4 search above). Revisit if a future release adds one. |
| `hooks/hermes_context_assembler_plugin` (registers `pre_llm_call`/`post_llm_call`) | **NATIVE mechanism, TTROS-owned handler** | Uses the standard Hermes plugin `register(ctx); ctx.register_hook(...)` API — same API the langfuse/nemo_relay first-party-adjacent plugins use. Survived the upgrade unpatched. |
| `hooks/b7_test_material_guard.py`, `hooks/runtime_guard.py` | **NATIVE mechanism, TTROS-owned logic** | Wired via `hooks.pre_tool_call` in `config.yaml` — the native shell-hook contract (stdin/stdout JSON, exit-2/`fail_closed` blocking, natively supported for `pre_tool_call`). Not a source patch. |
| `context_file_max_chars: 40000` (david config.yaml) | **KEEP — native key, TTROS-pinned value** | Confirmed exists unchanged post-upgrade (`agent/prompt_builder.py`); the value is TTROS's own pin against the dynamic per-model cap, not a patch. |
| `memory.write_approval: true` | **KEEP — native key, newly set** | `tools/write_approval.py`, native to v0.21.1 (present pre-upgrade too). |
| `memory.memory_enabled: true` / native MEMORY.md/USER.md | **NATIVE, per-profile design decision** | David keeps native memory alongside the Brain vault (unlike operator-lean, which disables it — `validate_unbound_runtime.py`'s `operator-lean:native_memory_disabled` check). Not something this step changes; recorded as-is. |
| `tools/context_assembler.py` (the assembler itself) | **TTROS-SPECIFIC — keep** | Business-Brain-note selection, client-scope isolation, provenance/audit blocks — no native equivalent; this is TTROS's own retrieval logic, only its *injection point* (`pre_llm_call`) is native. |
| `tools.tool_search.enabled: "off"` (operator-lean config.yaml) | **KEEP — native key, TTROS-pinned value** | New in v0.21.1, default `"auto"`. Pinned `"off"` for operator-lean only, to preserve its exact-enumerable bounded-tool-set contract (`operator_lean_oneshot.py::EXPECTED_TOOLS`) against the new deferred-tool bridge. Not evaluated for the other six profiles — none asserts an exact tool set the way operator-lean does, and none showed a test failure from it. |

## Prefix-size observation (no change made, recorded only)

For a generic probe request against David's profile (`classification: knowledge_sensitive`,
`write_artifact=False`, no queue side effect): stable-prefix blocks (`identity/company`,
`current priorities`, `executive_view`, `action boundaries`, `execution handoff contract`) =
**10,295 bytes / 2,125 tokens** across 5 blocks; dynamic blocks = 25,654 bytes / 5,959 tokens
across 10 blocks; **total assembled context = 36,017 bytes / 8,098 tokens.** This varies by
request/classification — recorded as one observed data point, not a fixed constant.

## Findings recorded, not acted on (out of STEP U's authorized scope)

1. **`session_search(profile=<other>)` cross-profile reads are silently broken** — opens the
   target `state.db` read-only, which leaves `SessionDB._fts_enabled` False (only set True on the
   read-write migration path), so every cross-profile discover/scroll query returns `count: 0`
   regardless of match, indistinguishable from "no results." Upstream `hermes_state.py` /
   `tools/session_search_tool.py`, not a TTROS component — patching it is outside AUTHORIZED.
2. **`tools/queue_mcp.py` does not exist on disk** though David's `config.yaml` still points
   `mcp_servers.queue` at it — pre-existing (already deleted in git status before this session
   started), not upgrade breakage. Not investigated or restored.
3. **`aos-nightly-hygiene.service`** is in `systemctl --user` `failed` state — noticed incidentally
   while checking service architecture for the restart question; unrelated to this step, not
   investigated.
4. The `TEST_MATERIAL_PATH_PATTERNS` defense-in-depth regex in `hooks/b7_test_material_guard.py`
   has an anchoring assumption (`(?:^|/)scripts(?:/|$)`) that a shell-command string breaks
   (see the `terminal` finding above) — it still functions as designed for bare-path tool inputs
   (`read_file`/`search_files`), just not for arbitrary command strings. Not changed; the
   name-based block is what actually closes the `terminal`/`process_manage` gap.

## PROOF checklist

- [x] `state.db` copy outside `~/.hermes` with matching sha256, taken before the upgrade.
- [x] Post-upgrade smoke result (7/7) equals pre-upgrade (7/7), after the two MCP-server repairs.
- [x] Five unrelated profiles hash identically pre/post (`unrelated_profiles.sha256` vs.
      `unrelated_profiles_post.sha256` — diff is empty).
- [x] B7 guard blocks during a simulated run and permits depth tools outside one; the check was
      made to FAIL first (`terminal`/`process_manage` unblocked pre-fix), then verified to PASS.
- [x] `git diff --check` clean apart from the two known pre-existing whitespace defects
      (`context/TOKEN_POLICY.md:94`, `hooks/token_budget_check.md:54`) — no new ones introduced.
- [x] No commit, no push (git log unchanged throughout this session).
- [x] Full repo suite, run twice (before and after the `operator-lean`/`tool_search` fix), for
      the population in this same run (not the stale 772/746/760 figures): **first run 807
      passed / 1 failed** (`test_live_loaded_operator_preamble_has_exact_bounded_tools_under_budget`);
      **second run: 808 passed / 0 failed**, after the fix.

## Files touched this session (all local, none committed)

- `agent/turn_context.py` (in `~/.hermes/hermes-agent`, outside this repo) — reapplied patch.
- `~/.hermes/profiles/david/config.yaml` (outside this repo) — added `memory.write_approval: true`.
- `~/.hermes/profiles/operator-lean/config.yaml` (outside this repo) — added
  `tools.tool_search.enabled: "off"`.
- `hooks/b7_test_material_guard.py` — `BLOCKED_TOOL_NAMES` re-derivation.
- `tools/brain_memory_mcp.py`, `tools/operator_lean_mcp.py` — `FastMCP` → `MCPServer`.
- `tools/operator_lean_oneshot.py` — deprecated `tools.mcp_tool` import → `tools.mcp_tool_discovery`.
- Removed a stale, month-old `.git/shallow.lock` in the hermes-agent checkout (lock artifact, not data).

Full evidence, transcripts, and the smoke-test instrument: `/home/liam/ttros_backups/hermes_upgrade_20260908/`.
