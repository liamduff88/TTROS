# STEP T2 — Hermes invocation audit and fixed-overhead decomposition. ZERO model calls.

Surface stated per block below (CLI-David, Gateway-David/dashboard, queue/orchestration). No
David/Hermes/provider call was made anywhere in this task. Every number is either read from a
pre-existing on-disk file (the same captured request dump T1 used, `state.db`, installed Hermes
package source) or computed locally by calling `tools/context_assembler.py`'s real functions
directly — never a `hermes` dispatch.

---

## PART 0 — WHICH PROFILE ACTUALLY RUNS

**Method:** grep across the repo, systemd user units, and the installed Hermes package's own
profile-resolution code (`hermes_cli/main.py`, `hermes_constants.py`). Zero model calls, zero
changes.

| # | Invocation site | Resolves to | How | Evidence |
|---|---|---|---|---|
| 1 | `scripts/step3_b7_harness.py`, `step5_b7_growth_harness.py`, `step6_b7_tools_harness.py` (the B7 harness) | `david` | explicit `-p david` in `subprocess.run([HERMES_BIN, "-p", "david", ...])` | e.g. `scripts/step3_b7_harness.py:522` |
| 2 | Dashboard `POST /api/dashboard/ask-david` → `_execute_named_profile_consultation("David","david",...)` → `_run_hermes_message(..., profile="david")` → `tools/aos-hermes-coordinator.sh --profile david` → `hermes -p "david"` | `david` | explicit at every hop | `dashboard/backend/main.py:7769`, `:4324-4332`, `:3967-3968`; `tools/aos-hermes-coordinator.sh:158-160` |
| 3 | `aos-morning-brief.service`/`.timer` → `python -m tools.aos_morning_brief --deliver` → HTTP POST to `/api/dashboard/ask-david` (localhost:8010) | `david` | same as #2, one hop upstream (HTTP, not CLI) | `tools/aos_morning_brief.py:36`; unit file `~/.config/systemd/user/aos-morning-brief.service` |
| 4 | Dashboard Executive Team consultations (`aos-orchestrator`, `aos-revenue`, `aos-marketing`, `aos-delivery`, `aos-ops`) — `_execute_executive_consultation` → `_execute_named_profile_consultation(member["name"], member["profile"], ...)` | the named executive's own profile, **not david** | explicit per member, by design | `dashboard/backend/main.py:4386-4388`, `_EXECUTIVE_TEAM` table |
| 5 | Queue worker execution, `owner=="hermes"` implementer path | `aos-orchestrator` | **implicit** — `_run_hermes_message`'s own Python default (`profile: str = "aos-orchestrator"`), no `profile=` kwarg passed at this call site; still explicit `--profile aos-orchestrator` at the shell boundary once inside `_run_hermes_message` | `dashboard/backend/main.py:9094-9099` (call site, no `profile=`); `:3936` (the default) |
| 6 | Queue worker execution, lane-routed path | named lane profile, else `aos-orchestrator` | explicit-with-fallback: `profile=str(route_metadata.get("profile_requested") or "aos-orchestrator")` | `dashboard/backend/main.py:9110` |
| 7 | Queue Hermes review (`_queue_run_hermes_review`) | `aos-orchestrator` | **implicit** — no `profile=` kwarg | `dashboard/backend/main.py:9270-9276` |
| 8 | Executive objective synthesis | `aos-orchestrator` | explicit | `dashboard/backend/main.py:9884-9889` |
| 9 | Operator-lean dashboard consultation | `operator-lean` | explicit `profile="operator-lean"`, `launcher=HERMES_OPERATOR_LEAN` → `tools/aos-hermes-operator-lean.sh` → hardcoded `export HERMES_HOME="$profile_home"` (env var, not `-p`) → in-process `hermes_cli.oneshot.run_oneshot` via `tools/operator_lean_oneshot.py` | `dashboard/backend/main.py:11276-11280`; `tools/aos-hermes-operator-lean.sh:8-9,104-105`; `tools/operator_lean_oneshot.py:73-83` |
| 10 | Hermes orchestration-plan coordinator | `aos-orchestrator` | **implicit** — no `profile=` kwarg | `dashboard/backend/main.py:12477-12480` |
| 11 | Direct dashboard "hermes-message" endpoint (chain/objective decomposition) | `aos-orchestrator` | **implicit** — no `profile=`, no `launcher=` kwarg at all | `dashboard/backend/main.py:12736` |
| 12 | `tools/source_intake_semantic.py` (STEP I1 ingestion) | `source-intake-semantic` | explicit `["hermes","-p","source-intake-semantic",...]`, module constant `HERMES_PROFILE` | `tools/source_intake_semantic.py:42,190` |
| 13 | `tools/aos-queue.py::probe_profile_invocation` | N/A — **never dispatches a model.** Read-only `hermes profile show` probe only; its own docstring: *"No invocation is simulated: `invoked` remains false until an actual model run reports usage."* References a `DEFAULT_PROFILE = "default"` string for lane-routing display | `tools/aos-queue.py:617,667-676` |
| 14 | `aos-nightly-hygiene.service` (`tools.nightly_knowledge_hygiene`) | none | file's own header: *"It never invokes a model."* Confirmed no `hermes`/subprocess reference in the file | `tools/nightly_knowledge_hygiene.py:8` |
| 15 | `aos-gmail-capture.service` (`tools/aos_capture_live.py poll`) | none | delegates to `aos_capture.py`; only reference found is a `"model_confirmed": "no-agent-invocation"` marker | `tools/aos_capture.py:690` |
| 16 | `aos-runner.service` (`tools/aos-orchestration-runner.py --watch`) | not itself | makes HTTP calls (`urllib.request.urlopen`) into the dashboard backend's queue endpoints, which resolve per rows 5–11 above | `tools/aos-orchestration-runner.py:186` |
| 17 | `connectors/telegram_bridge/`, `workspaces/north_shore_sales_coach/` (`aos-bridge.service`, `aos-north-shore.service`) | **not established — protected path, access denied.** This session's permission settings refused both `Bash` and `Read` into these directories even for a read-only audit grep. Per CLAUDE.md these remain protected unless Liam explicitly scopes them; this task did not, so the gap is reported rather than bypassed. | tool-level `PermissionError`/denial when attempting to read either directory |
| 18 | `aos-cloudflared.service` | none — tunnel process only | — | unit file |

**One-line answer: NO** — not every TTROS path that reaches Hermes resolves to `david`. By
design, several legitimate non-`david` profiles exist and are in active use: `aos-orchestrator`
(queue/worker execution, rows 5,7,10,11), `aos-revenue`/`aos-marketing`/`aos-delivery`/`aos-ops`
(Executive Team, row 4), `operator-lean` (dashboard operator surface, row 9), and
`source-intake-semantic` (ingestion, row 12). Every path that **is** intended to reach David
(CLI-David row 1, Gateway/dashboard-David rows 2–3) resolves explicitly with no implicit
fallback anywhere in the chain — the implicit defaults that do exist (rows 5, 7, 11) all resolve
to `aos-orchestrator`, never silently to `david` or to the unnamed root profile.

**A real, named risk class exists in the installed Hermes package itself, though no TTROS site
hits it today:** if `hermes` is ever invoked with neither `-p`/`--profile` nor an explicit
`HERMES_HOME` env var, it silently falls back to `~/.hermes` itself (the literal Hermes-internal
"default profile," not any `~/.hermes/profiles/<name>/` directory — `~/.hermes/profiles/default/`
does not exist on disk). Hermes's own code names this exact failure mode and emits a warning for
it (`hermes_constants.py:54-89`, `_warn_profile_fallback_once`, referencing upstream issue
`#18594`: *"HERMES_HOME is unset but active profile is ...  Falling back to ..., which is the
DEFAULT profile ... Any data this process writes will land in the wrong profile."*). Every
dispatch site enumerated above passes an explicit selector (`-p <profile>` or a hardcoded
`HERMES_HOME=` export) at the point it actually invokes Hermes, so this fallback is not observed
to occur anywhere in TTROS today — named as the cautionary precedent it is, per CLAUDE.md's own
framing of the b7-hook-allowlist gap, not as a live defect.

---

## PART 1 — THE 29 NATIVE TOOLS: full table, call counts, subtotals

**Evidence:** the same captured request dump T1 used
(`~/.hermes/profiles/david/sessions/request_dump_20260909_191615_f3a237_20260909_191627_264463.json`).
Bytes below use Python's default `json.dumps()` separators (`, `/`: `), confirmed to reproduce
T1's own 40,088 B tools-array figure and 94,102 B whole-body figure exactly (compact
separators give 39,098/93,082 B — a different, also-valid measurement, but not T1's instrument;
this report reuses T1's instrument per CLAUDE.md).

**Tool-call source:** `state.db`'s `messages` table, all 21 post-I3 B7 sessions (session ids
resolved from `scripts/step6_post_i3_b7_pass_{A1..E4}.usage.json`; the 4 failed sessions E5/F1/F2/F3
excluded, matching T1's own "21-question pass" scope). `messages.tool_calls` already records the
literal native tool name per call (`tool_call`, `tool_describe`, `skill_view`, `read_file`) — no
dispatcher-wrapper unwrapping was needed for *this* table, since these four names are themselves
native tools, not a generic proxy shape. (The wrapper **was** unwrapped one level further, out of
curiosity/completeness: all 35 `tool_call` invocations proxy `mcp__brain__*` tools — 19
`open_note`, 7 `search_history`, 4 `search_calls`, 4 `open_call`, 1 `list_resources` — confirming
none of the 29 native tools' own byte cost was displaced onto brain-tool traffic.)

| Bytes | Tool | Calls (21-session pass) | One-line purpose (from the tool's own schema) |
|---:|---|---:|---|
| 4,414 | `delegate_task` | 0 | Spawn subagents in isolated contexts, each with its own conversation/terminal/toolset. |
| 3,374 | `terminal` | 0 | Execute shell commands. |
| 3,299 | `memory` | 0 | Save durable facts to persistent memory injected into every future turn. |
| 3,012 | `execute_code` | 0 | Run Python that calls Hermes tools programmatically (3+ tool calls with logic between them). |
| 2,492 | `tool_search` | 0 | Search deferred (MCP/plugin) tools loaded on demand. |
| 2,390 | `skill_manage` | 0 | Create, update, or delete skills. |
| 2,332 | `search_files` | 0 | Search file contents or find files by name (ripgrep-backed). |
| 1,886 | `text_to_speech` | 0 | Convert text to speech audio. |
| 1,640 | `patch` | 0 | Targeted find-and-replace file edits (fuzzy matching). |
| 1,639 | `clarify` | 0 | Ask the user a clarifying question before proceeding. |
| 1,197 | `browser_vision` | 0 | Screenshot the current browser page for visual inspection. |
| 1,169 | `read_file` | **1** | Read a text file with line numbers and pagination. |
| 1,119 | `web_extract` | 0 | Extract clean page content (markdown/text) from a URL. |
| 1,012 | `browser_console` | 0 | Get browser console output / JS errors. |
| 966 | `browser_snapshot` | 0 | Text-based accessibility-tree snapshot of the current page. |
| 945 | `browser_navigate` | 0 | Navigate the browser to a URL. |
| 932 | `skill_view` | **13** | Load a skill's full content. |
| 898 | `write_file` | 0 | Write/replace a file's content. |
| 848 | `vision_analyze` | 0 | Load an image into the conversation to see it. |
| 797 | `web_search` | 0 | Search the web. |
| 525 | `tool_call` | **35** | Invoke a deferred (lazily-discovered) tool by name. |
| 507 | `browser_type` | 0 | Type text into a browser input field. |
| 499 | `tool_describe` | **14** | Load full JSON schemas for tools returned by `tool_search`. |
| 468 | `browser_click` | 0 | Click a browser element by ref ID. |
| 412 | `browser_scroll` | 0 | Scroll the browser page. |
| 401 | `browser_press` | 0 | Press a keyboard key in the browser. |
| 317 | `browser_get_images` | 0 | List images on the current browser page. |
| 308 | `skills_list` | 0 | List available skills (name + description). |
| 232 | `browser_back` | 0 | Navigate back in browser history. |

**Three groups, byte subtotals (sum reconciles exactly to 40,030 B; +58 B of array
brackets/commas = the full 40,088 B tools-array figure):**

| Group | Tools | n | Bytes |
|---|---|---:|---:|
| Called more than once | `tool_call`(35), `tool_describe`(14), `skill_view`(13) | 3 | 1,956 |
| Called exactly once | `read_file`(1) | 1 | 1,169 |
| Never called | the other 25 (all `browser_*`, `clarify`, `delegate_task`, `execute_code`, `memory`, `patch`, `search_files`, `skill_manage`, `skills_list`, `terminal`, `text_to_speech`, `tool_search`, `vision_analyze`, `web_extract`, `web_search`, `write_file`) | 25 | 36,905 |

**Reading this plainly:** 25 of 29 native tools (36,905 B, 92% of the tools-array) were never
called once across 21 real knowledge/history/executive questions. This is consistent with, and
sharper than, T1's framing — it is not "most tools are marginal," it is "all but 4 are unused in
this pass," with the important caveat T1 and this task both name: **this pass covered A–E4
knowledge questions only; execution/queue/connector paths that would exercise `terminal`,
`write_file`, `delegate_task`, etc. were never in scope for these 21 sessions**, so "never called
here" is not the same claim as "never needed by David."

---

## PART 2 — THE 27,384 B OF `instructions`: segment decomposition

Exact byte boundaries located by scanning the captured `instructions` string for its own markdown
headings and XML-style tags; every segment below reconciles to the whole to the byte.

| Bytes | Segment | Origin |
|---:|---|---|
| 6,708 | SOUL.md persona (`# David` … before `# Finishing the job`) | **TTROS** — `~/.hermes/profiles/david/SOUL.md`, 6,099 B on disk. The 609 B (~10%) growth in situ is Hermes-side whitespace/markdown reflow, not content growth (spot-checked: same headings, same prose). |
| 9,753 | Hermes framework boilerplate (`# Finishing the job` … before `## Skills`: Parallel tool calls, Skill Safety Rule, Mid-turn user steering, Tool-use enforcement, Execution discipline — `tool_persistence`/`mandatory_tool_use`/`act_dont_ask`/`prerequisite_checks`/`verification`/`external_state_verification`/`literal_preservation`/`missing_context`) | Hermes-constructed |
| 1,073 | "## Skills" lead-in ("Before replying, scan the skills below... Err on the side of loading...") | Hermes-constructed |
| 8,656 | native `<available_skills>` catalog (~80 generic Hermes skills — ComfyUI, PowerPoint, TouchDesigner, xlsx, etc.) | Hermes-constructed |
| 84 | closing sentence ("Only proceed without loading a skill if genuinely none are relevant...") | Hermes-constructed |
| 379 | MEMORY block (banner + this session's actual memory content: *"User asked David to remember the word: banana."*, 46 chars) | Hermes-constructed banner; content is session/user data via the native `memory` tool, not a TTROS file |
| 122 | session metadata (Conversation started / Model / Provider / Platform lines) | Hermes-constructed |
| 609 | `# Hermes runtime environment` (WSL host, cwd, `/mnt/` mount note) | Hermes-constructed |
| **27,384** | **sum** | matches captured `instructions` bytes exactly |

**Only the 6,708 B persona segment (24.5%) is TTROS-authored.** The remaining 20,676 B (75.5%) is
Hermes's own construction — the great majority of it (8,656 B, 31.6% of the whole `instructions`
block) is the native skills catalog, which T1 already flagged as almost entirely irrelevant to an
ordinary TTROS business question and outside `context_assembler.py`'s reach. The MEMORY segment
is real but tiny in this capture (46 characters of actual content inside a 379 B banner) — not
representative of every request, since native-memory content grows with what David has been asked
to remember, but structurally small regardless (`context_file_max_chars: 40000` design cap
notwithstanding, this session's David memory sits at 2%/2,200 chars per the banner's own
declaration).

---

## PART 3 — WHAT THE INSTALLED HERMES (v0.21.1, 2026.9.7) ACTUALLY SUPPORTS

T1 checked the `mcp_servers:` block for eager/preload/schema options and correctly found none
there. **That was the wrong surface.** The real mechanism sits in two other places entirely.

### Q1 — Can native tools be scoped (allowlist/denylist/per-tool/toolset)? **YES.**

Two independent, composable mechanisms, both real and already load-bearing in this repo:

1. **`agent.enabled_toolsets` / `agent.disabled_toolsets`** — named tool-group subtraction.
   `hermes_cli/toolsets.py:69-115` (the `TOOLSETS` registry: `web`, `browser`, `terminal`,
   `skills`, `file`, `vision`, etc., each a fixed list of native tool names).
   `model_tools.py:280-334` (`_apply_toolset_selection`/`_select_tool_names`) applies
   `disabled_toolsets` as a strict end-of-pipeline subtraction (comment cites upstream issues
   `#17309`/`#64503`), wired from config through `agent/agent_init.py:1049,2156,2181,2281
   (_load_tools)`. Individual-tool granularity is reachable by wrapping a single tool name in a
   **custom toolset** (`toolsets.py:438 create_custom_toolset`) and disabling that.
2. **`tools.tool_search.enabled`** ("auto"/"on"/"off") — governs whether deferrable (MCP/plugin)
   tools are hidden behind the `tool_search`/`tool_describe`/`tool_call` bridge (the lazy-discovery
   pattern T1 correctly identified) or included **eagerly, with full schemas, directly in the
   model-facing tools array**. Default `"auto"`. `"off"` = *"pass-through, no bridge"* — this is
   the literal eager-preload switch T1's Repair 3 looked for and, checking the wrong config
   section, concluded did not exist. `hermes_cli/config_defaults.py:1789-1817`
   (schema/default/docstring); `model_tools.py:464-480` (`_compute_tool_definitions`, `ts_cfg.enabled
   != "off"` gate). Core tools (the 29 in Part 1) are explicitly documented as *"NEVER deferred"* —
   this switch only affects MCP/plugin tools like TTROS's own `mcp__brain__*`.

### Q2 — Per profile, or global? **PER PROFILE**, confirmed three independent ways:

- Config is loaded from `get_hermes_home()/config.yaml` (`hermes_cli/config.py:491-493,2178-2181`),
  and `-p <profile>` (or an explicit `HERMES_HOME=` export) sets `HERMES_HOME` to that specific
  profile's own directory before any config is read (`hermes_cli/main.py:414-441
  _scan_profile_flag`; `hermes_constants.py:82-89 get_hermes_home`).
- **Direct, already-live precedent in this repo:** `tools.tool_search.enabled: "off"` is set in
  `~/.hermes/profiles/operator-lean/config.yaml` and **nowhere else** — TTROS's own STEP U
  closeout (`scripts/hermes_upgrade_and_native_capability_classification.md:270-273`) states
  explicitly: *"Pinned `"off"` for operator-lean only ... Not evaluated for the other six
  profiles."* David's own `~/.hermes/profiles/david/config.yaml` (read directly this session,
  reproduced above) has no `tools:` block at all — it inherits the global default (`"auto"`).
- Global-only would be an automatic no-change per this task's own framing; it is not global.

### Q3 — Can the native `available_skills` catalog be scoped/suppressed per profile? **YES.**

The catalog's injection is gated on whether `skill_view` is in the active tool set:
`agent/prompt_builder.py:141` — *"Injected only when skill_view exists AND the hermes-agent skill
is installed"* — and `:151` names the exact suppressed variant used when it is not: *"Variant for
sessions without the skills toolset (e.g. Blank Slate): naming skill_view() there would dangle."*
The catalog itself is built in `agent/prompt_builder.py:1195-1330`
(`build_skills_system_prompt`/`_render_skills_index`). Disabling the `skills` toolset
(`disabled_toolsets: [skills]`) removes `skill_view`/`skill_manage`/`skills_list` from the tool
array and, per the gate above, suppresses the 8,656 B catalog from `instructions` — per-profile,
same mechanism as Q1/Q2.

### Q4 — Did either change across the STEP U upgrade? **YES, for the eager/deferred mechanism.**

`tools.tool_search.enabled` **is new in v0.21.1** — it did not exist in v0.18.0. TTROS's own STEP
U closeout documents discovering this the hard way: the upgrade silently collapsed operator-lean's
exact bounded tool contract until this key was added
(`scripts/hermes_upgrade_and_native_capability_classification.md:8,25-26,184-200`: *"Hermes v0.21.1's
new tool-search virtualization (`tools.tool_search`, default `"auto"`) collapsed every tool the
operator-lean [profile expected]..."*). **This means the eager-preload lever T2 is asking about was
introduced by the very upgrade T1's own predecessor audit (STEP U) already fixed for one profile
(operator-lean) but never carried over to David** — not a gap in Hermes, a gap in which profile
got the fix applied. The `disabled_toolsets`/`TOOLSETS` registry mechanism (Q1's first lever) is
not documented as new in STEP U's closeout; its cited upstream issue numbers (`#17309`/`#64503`)
are not dated in this repo's evidence, so whether it predates v0.18.0 is not established here.

### Q5 — A supported hook/plugin point that filters the tools array pre-dispatch? **NO.**

`VALID_HOOKS` (`hermes_cli/plugins.py:107-188`) includes `pre_api_request`/`pre_llm_call`, but
both are documented, observer-only telemetry hooks (`docs/observability/README.md:100-140`):
`pre_llm_call` may only return a string/`{"context":...}` to *inject* ephemeral context;
`pre_api_request` receives a *"sanitized request payload"* for logging, with no return-value
contract to mutate it. The plugin-registration API's `allow_tool_override`
(`hermes_cli/plugins.py:448-491`, `plugin_capabilities.py:28-31`) lets a consenting plugin **add or
replace** one named tool's implementation — it has no bulk-remove/filter operation. The only real
lever for shrinking the array is the config-level mechanism in Q1/Q2 — which is config, not a
hook, and requires no patching or forking of Hermes to use.

---

## PART 4 — APPLY? BOTH PRECONDITIONS STATED

- **PRECONDITION 1** (native-tool scoping exists and is per-profile): **MET.** Established in
  Part 3 above, with a live in-repo precedent (operator-lean's own `tools.tool_search.enabled:
  "off"`).
- **PRECONDITION 2** (every TTROS path reaching Hermes resolves to `david` explicitly): **NOT
  MET.** Established in Part 0: `aos-orchestrator`, `aos-revenue`/`aos-marketing`/`aos-delivery`/
  `aos-ops`, `operator-lean`, and `source-intake-semantic` are all real, currently-active,
  by-design non-`david` profiles reached from this repo.

**Decision: NO CHANGE.** Per this task's own instruction — *"If either is NO, do not change
anything... An unnamed profile means we cannot know which configuration is in play, and we have
no business changing what a profile carries until we do."* — `david/config.yaml` was not touched.
No `disabled_toolsets`, no `tools.tool_search.enabled`, nothing. This is reported as a finding,
not a partial fix: **the mechanism T1 said didn't exist, does exist and is already proven safe on
one TTROS profile (operator-lean); this task is not the one authorized to extend it to David**,
because Part 0's multi-profile reality — a real, useful, load-bearing feature of this system, not
a defect — means "every path resolves to david" is false on its face, and that was the literal
gate this task set for itself before touching config.

No new tools bytes, no new total, no delta — config is byte-identical to before this task ran.

---

## PART 5 — BOUND THE DYNAMIC SIDE

### The ~13 KB Fred-vs-Andrea gap, block by block (fresh same-run measurement, zero model calls)

T1's own cross-reference (25,363 B for E5, 43,414 B for Fred, from two different points in its own
pass) is not directly diffable block-by-block, since morning-findings/session-recency content
drifts between runs by design (it's relevance-filtered against live, growing state). This task
re-ran both questions **in the same script execution, against the current live index**, which
reproduces the same ~13 KB magnitude and is internally diffable to the byte:

| Block | Andrea (E5) | Fred/MLS | Δ (Fred − Andrea) |
|---|---:|---:|---:|
| identity/company | 3,002 | 3,002 | 0 |
| current priorities | 1,923 | 1,923 | 0 |
| executive_view | 1,667 | 1,667 | 0 |
| **deterministic morning findings** | 99 | 6,124 | **+6,025** |
| scoped canonical Brain notes | 4,651 | 4,966 | +315 |
| recent receipts and outcomes | 54 | 54 | 0 |
| **relevant session recency** | 981 | 4,348 | **+3,367** |
| relevant open loops | 52 | 52 | 0 |
| relevant current commitments | 63 | 1,183 | +1,120 |
| matching skills/workflows | 8,142 | 9,354 | +1,212 |
| conversation summary | 784 | 784 | 0 |
| action boundaries | 537 | 537 | 0 |
| execution handoff contract | 3,166 | 3,166 | 0 |
| queue reference validity | 532 | 883 | +351 |
| provenance | 1,993 | 2,594 | +601 |
| **Sum of blocks** | 27,646 | 40,637 | **+12,991** |

**Reading:** `deterministic morning findings` (+6,025 B, 46% of the gap) and `relevant session
recency` (+3,367 B, 26%) together explain 72% of the growth — both are legitimately
relevance-filtered, request-variable blocks, exactly as T1's Part 1 hypothesis-testing found for
the morning-findings block specifically (near-zero for a narrow relationship question, large for
a broader one). `matching skills/workflows` adds a further 1,212 B (9%) — smaller than the other
two but still substantial and, per the range measurement below, not obviously earning its size.
The full rendered `input[0].content` for Fred (via `AssembledContext.render()`, the actual
marker-header + per-block-header text that reaches the wire) measured **43,436 B** — 22 B off
T1's own 43,414 B, a difference fully attributable to `invocation_id`/`session_id` string-length
variance between runs (the render includes both verbatim), not a code or content change.

### `matching skills/workflows` across eight question shapes (zero model calls)

| Question shape | Bytes | Tokens | Selected IDs (top hits) |
|---|---:|---:|---|
| Trivial conversational ("Thanks, that is helpful.") | 28 | 8 | *(none — zero matches)* |
| CCI ("What happened with CCI?") | 28 | 8 | *(none — zero matches)* |
| Fallback/broad executive | 7,423 | 1,600 | — |
| Andrea (E5, relationship/history) | 8,142 | 1,675 | — |
| Negative control ("client work items in human review?") | 8,667 | 1,808 | `client_memory`, `build_client_memory`, `aoa_working_session`, `weekly_review` |
| History, different shape ("Kenneth across all our calls") | 8,495 | 1,775 | — |
| Executive/strategy ("core principle behind how we sell") | 8,994 | 1,841 | `morning_brief`, `source-intake`, `fit_call_prep`, `quick_win_scan` |
| Fred/MLS | 9,354 | 1,857 | — |

**Range: 28 B – 9,354 B (8 – 1,857 tokens), a ~330× spread.** The block is not weakly present —
it fires (near-)fully (selects 4/30 candidates, its fixed cap) on 6 of 8 shapes including a
deliberately unrelated negative control, and goes to exactly zero on 2 of 8 for no principled
reason distinguishable from the other zero-hit cases at a glance. Root cause, read directly from
the selector: `_matching_workflows_block` (`tools/context_assembler.py:1066-1081`) scores every
`*/SKILL.md` and `*/workflow.md` file by **counting query-term occurrences anywhere in the whole
document body** (`lowered.count(term)`, no title/frontmatter restriction, no minimum score, no
term-length/strength gate), then takes the top 4 unconditionally. This is the same class of defect
Repair 2 fixed for card selection in T1 (whole-document substring matching producing
keyword-collision false positives) — but **no equivalent precision gate exists here.** The negative
control's own selection (`client_memory`, `build_client_memory`, `aoa_working_session`,
`weekly_review` for a pure queue-count question) and the executive/strategy question's selection
(`morning_brief`, `source-intake`, `quick_win_scan` for a sales-philosophy question) are both
concretely, inspectably marginal — evidence the block is large *and* weakly relevant across the
range, not an assumption.

**Proposed bound, not applied (Step 8's call):** apply the same precision-gate pattern already
proven in Repair 2 — score against title/frontmatter/filename stem rather than full document
body, require a minimum term-length/strength threshold before a candidate counts, and consider
lowering the fixed top-4 cap or gating it on a minimum score rather than always filling to 4
regardless of match quality.

---

## ACCEPTANCE

T1's own six-case set, re-run unchanged against the current live code and index (zero model
calls, `assemble()` called directly) — **all six still hold, byte-identical card selection to
T1's own table:**

| Case | Cards selected | Bytes |
|---|---|---:|
| Fred/MLS | `d9cb4668...`.card.md, `kenneth-meeting-may-27`.card.md | 4,966 |
| CCI | `call-kenneth-after-first-cci`, `first-call-cci`, `cci-second-call-june-15` | 7,262 |
| Andrea (E5) | `andrea-roberts-june-26`, `andrea-second-call-june-30` | 4,651 |
| Negative control 1 | *(none)* | 192 |
| Negative control 2 (trivial) | *(none)* | 192 |
| Fallback control | *(none)* | 192 |

No regression — expected, since **no code changed** in this task (Part 4 made no edit; nothing in
`context_assembler.py`, config, or elsewhere was touched).

**New total request size for Fred:** full rendered assembled-context (43,436 B) + question
already included + `instructions` (27,384 B, unchanged, assumed stable per T1's own stated
assumption) + `tools` (40,088 B, unchanged) = **110,908 B**, vs. T1's own 110,886 B (**+22 B,
+0.02%** — invocation-id-length noise, not a change) and vs. the 94,102 B original baseline
(**+16,806 B, +17.9%**, identical in kind to T1's own finding since nothing was changed: the
increase is the same genuinely-relevant retrieved evidence T1 added in Repair 2, not new bloat).

---

## REGRESSION

**Focused suite** (T1's own set, `.venv/bin/python3 -m pytest ... -q`): **77 passed, 2 failed, 30
subtests passed** — same two tests T1 named, confirmed still isolated to those two:
`tests/test_one_brain_context.py::...test_revenue_entities_and_activity_are_selected_automatically`
and `tests/test_hermes_context_plugin.py::...test_unregistered_profile_receives_no_context`.

**Resolving the two conflicting descriptions of "T1's single failing test":** they are **two
different tests**, not one — T1's own document is internally consistent about this but its
closeout line ("the 1 failure is...") reads ambiguously in isolation. Verified directly this
session, with both the focused-subset run and a real full-suite run in hand:
- `test_revenue_entities_and_activity_are_selected_automatically` fails with
  `ClientScopeError: Business Brain pointer does not belong to global:
  business_brain:sources/intake/INDEX.md` — the graph-scope registry gap T1 named. It fails in
  the focused-subset run (confirmed, matches T1 exactly) and **also fails when run completely
  alone** (`pytest tests/test_one_brain_context.py::ContextAssemblerTests::test_revenue_entities_and_activity_are_selected_automatically`
  by itself). It is real and reproducible outside the full suite, and not caused by this task or
  T1's edits (`client_scope_registry`/`business_brain_graph.py` were not touched by either).
- `test_unregistered_profile_receives_no_context` fails with `PermissionError: [Errno 13]
  Permission denied: hooks/context_assembler_hook.py` — a file-permission gap, unrelated to the
  first test, on a file neither T1 nor this task edited (mode `100644` per T1, unchanged).
- **The full suite (run to completion this session, see below) confirms T1's own claim
  exactly: only the permission-gap test fails; the graph-scope test passes.** So T1's
  "test-order/isolation-dependent" characterization is correct, not mis-stated — something
  earlier in full-suite execution order leaves the client-scope registry (or a shared fixture) in
  a state where the graph-scope test passes, that state isn't present when the test runs alone or
  inside the smaller focused-subset file selection. **The resolution: these are two distinct,
  separately-reproducible failures, not one test with two descriptions** — the graph-scope one is
  order-dependent (fails alone/focused-subset, passes full-suite) and the permission one is not
  (fails everywhere, every run, this session included).

**Full suite** (`.venv/bin/python3 -m pytest -q`, run to completion this session, 392.93s):
**828 passed, 1 failed, 223 subtests passed.** The 1 failure is
`test_hermes_context_plugin.py::HermesContextPluginTest::test_unregistered_profile_receives_no_context`
(the file-permission gap) — `test_revenue_entities_and_activity_are_selected_automatically` passed
in this run, exactly as T1 reported and as the order-dependence explanation above predicts.

**`git diff --check`:** exit 2, two pre-existing whitespace findings —
`context/TOKEN_POLICY.md:94` and `hooks/token_budget_check.md:54`, both "new blank line at EOF,"
both already present in the dirty tree before this task started and untouched by it.

**Test population reconciliation:** `pytest --collect-only -q` → **829 tests collected**,
identical to T1's own figure — no drift since T1 ran. Explained exactly as T1 explained it: one
deletion (`tests/test_aos_dashboard_cleanup.py`), three additions
(`tests/test_b6_source_disposition.py`, `tests/test_b7_test_material_guard.py`,
`tests/test_validation_a_seal_guard.py`), net +2 against the 772/804 baseline named in CLAUDE.md —
confirmed directly against current `git status`, not re-derived from T1's prose. **The earlier
565 → 772/804 movement predates both T1 and this task's evidence base and is not independently
re-derived here** — named as unexplained-by-this-task rather than assumed benign.

---

## CLOSEOUT

**Model calls: 0. David/Hermes/provider turns: 0.**

**Part 0:** NO, not every path resolves to `david` — five other legitimate, by-design profiles
are in active use (`aos-orchestrator`, four Executive Team profiles, `operator-lean`,
`source-intake-semantic`). Every path that *is* meant to reach David does so explicitly, with no
implicit fallback anywhere in the chain.

**The 29 tools:** 25 of 29 (36,905 B) never called once across the 21-question A–E4 pass; 3
tools (`tool_call`, `tool_describe`, `skill_view` — 1,956 B) called repeatedly; 1
(`read_file`, 1,169 B) called once.

**`instructions`:** only 6,708 B (24.5%) is TTROS's own SOUL.md; 8,656 B (31.6%) is Hermes's
native skills catalog; the rest is Hermes framework boilerplate/runtime metadata.

**Hermes capability:** native-tool scoping exists and is per-profile — via
`disabled_toolsets`/`enabled_toolsets` **and**, newly identified this task,
`tools.tool_search.enabled` (the real eager/lazy-MCP switch, new in v0.21.1, already proven on
operator-lean but never extended to david). The skills catalog can be suppressed the same way. No
hook/plugin point can filter the tools array pre-dispatch without this same config mechanism.

**Part 4: NO CHANGE.** Precondition 1 (mechanism exists, per-profile) — MET. Precondition 2
(every path resolves to david) — NOT MET. Per the task's own gate, nothing was touched.

**Dynamic side:** the ~13 KB Fred/Andrea gap is 72% two blocks (`deterministic morning findings`
+6,025 B, `relevant session recency` +3,367 B), both legitimately request-variable.
`matching skills/workflows` ranges 28 B–9,354 B across 8 shapes (a ~330× spread) and is
concretely, inspectably weakly relevant on at least 2 of 6 non-zero hits (verified selections
named above) — a precision-gate bound is proposed, not applied, per this task's Step-8 boundary.

**Acceptance:** all six T1 cases still hold, byte-identical selections. Fred total: 110,908 B vs.
T1's 110,886 B (+0.02%, invocation-id noise) vs. 94,102 B baseline (+17.9%, unchanged in kind from
T1's own finding since no code changed).

**Tests:** focused suite 77/79 passed; full suite **828/829 passed** (392.93s) — the 1 failure is
the pre-existing `hooks/context_assembler_hook.py` permission gap, confirmed untouched by this
task. The second focused-subset failure (graph-scope `ClientScopeError`) is confirmed
order-dependent — passes in the full suite, fails standalone/focused — not a regression, not
caused by this task. Population 829, unchanged from T1, reconciled against CLAUDE.md's 772/804 via
git status directly (net +2 test files: −1 deleted, +3 added).

**The largest remaining fixed cost, named, and why this task did not reach it:** the 40,088 B
native tool-definition array (36,905 B of it evidenced-unused in this pass) is **now confirmed
technically reachable** — `tools.tool_search.enabled`/`disabled_toolsets`, both per-profile,
both already proven safe on operator-lean — but this task's own Part 0 gate correctly stopped it
from being touched on David's profile, because David is one of six-plus profiles genuinely in
play and this task never got instruction-level authorization to decide which of those six should
be narrowed first, or whether narrowing David specifically (vs. leaving it deliberately
full-capability, since Executive-Team/queue paths already use restricted profiles) is even the
right call. That decision — not a technical blocker — is what stands between here and applying
it.

No commit. No push.
