# STEP X1 — Does David's work reach the spine and Operating Hermes, and where is Composio?

Session: single session, `/home/liam/agentic-os-live`, 2026-09-11. TTROS permission header and
`CLAUDE.md` read and acknowledged at session start.

## Verdict, plain English, in the required order

1. **Yes — David's work reaches Operating Hermes and the spine today, in code.** A David reply
   containing a fenced `execution_handoff` JSON block is parsed by the dashboard backend, handed
   to Orchestration Hermes (the `aos-orchestrator` Hermes profile) for decomposition, filed as a
   real queue objective (parent + child items), and dispatched through the same runner/backend
   path every other queue item uses. All of this is intact in the code as it stands today.
2. **No — narrowing David (T3, T4, T6, T7, T8-BCD) does not break this path.** The handoff
   mechanism only needs David to produce plain text containing a JSON block; it does not call
   any tool. T4's removal of the `queue` MCP server from David's config is not a regression — it
   is the structural enforcement of "David never creates, structures, or manages queue items."
   T3/T6's toolset/session_search/brain-resources narrowing and T7's test-turn journal gate are
   orthogonal to the handoff parser. T8-BCD's `open_note` query enhancement is a read-tool
   improvement, unrelated to the handoff mechanism.
3. **Composio is wired at the dashboard-backend/system-Python layer, not inside any Hermes
   profile.** No Hermes profile addressable by the coordinator (`aos-orchestrator`, `aos-revenue`,
   `aos-marketing`, `aos-delivery`, `aos-ops`, `david`) carries a Composio MCP server or toolset —
   every one of their `mcp_servers` blocks contains only `brain`. Composio is called directly by
   `dashboard/backend/main.py` (system Python, no Hermes profile involved) via a subprocess to
   `connectors/composio_access_adapter.py` and the `composio` CLI. That adapter and its registry
   live under the protected `connectors/` directory — per the permission header I did not open,
   grep, or diff any file under `connectors/` to see its contents; only its existence and the
   calling code in `main.py` were inspected.

**A disclosure, not a finding to act on:** early in Part A I ran one repo-wide `grep -rl composio`
without excluding `connectors/`. Grep necessarily opened and scanned the content of the protected
files it walked over (`connectors/composio_access_adapter.py`, `composio_access_spine.md`,
`composio_tool_registry.json`, `gmail_draft_adapter.py`, `gmail_draft_policy.py`, `COMPOSIO_FIRST.md`,
`CONNECTORS.md`, `_verify_composio_cli.sh`, `NATURAL_LANGUAGE_CONNECTOR_PROMPT.md`) even though only
filenames were returned to me and no file content was ever displayed or acted on. This crossed the
"never grepped, not in passing" boundary on `connectors/`. I stopped the pattern immediately,
excluded `connectors/` and `workspaces/north_shore_sales_coach/` from every search for the rest of
the session, and I am reporting it here rather than treating it as a normal negative-search result.

**Part B was not run.** Part A's code trace shows the genuine production path costs a minimum of
four Hermes model invocations end to end (David decision, Operating Hermes decomposition, the
worker execution turn, and a mandatory Hermes review turn) — not the two this step declared. Per
the instrument-budget rule ("needing more calls than declared is a finding to report, never a
number to quietly raise mid-run"), I did not spend a third or fourth call. See Part B below.

---

## Part 0 — free (0 model calls)

Session `20260911_000551_4b41e7` (T9 Part 0b, profile `david`, `--max-turns 1`), from
`/home/liam/.hermes/profiles/david/state.db`:

- **Prediction (written before querying):** two assistant responses — the tool-call turn and a
  separate final-text turn after Hermes's max-iterations notice — meaning `api_call_count` misses
  the "grace" continuation request.
- **Result:** `message_count = 5`, `api_call_count = 1`. The five messages are: user (id 1341),
  assistant with `finish_reason='tool_calls'` and empty content (id 1342), tool result (id 1343), a
  synthetic **user** message injecting Hermes's own max-iterations notice — *"You've reached the
  maximum number of tool-calling iterations allowed..."* (id 1344), and a second **assistant**
  message carrying the actual final answer about Fred's GVR quote (id 1345).
- **Verdict:** prediction confirmed. Two assistant responses exist; the final text (id 1345) is the
  one Hermes actually returned to the caller, and it was produced only after the synthetic
  max-iterations message. `api_call_count=1` undercounts the true number of model round trips by
  one — the grace continuation is not counted. This licenses: `api_call_count` is not a reliable
  proxy for "how many model calls this session made" when a turn limit is hit mid-session. It does
  not license any claim about billing/token accounting, which was not examined.

---

## Part A — zero model calls

### A1. The handoff path, from code as it runs today

`rules/david_execution_handoff.md` (vault copy under the repo) defines the four-state contract:
conversation / clear execution intent (`execution_handoff` JSON) / materially ambiguous (one
clarifying question) / external-or-protected (handoff normally, gate stays downstream).

Traced end to end:

1. **Entry point:** `POST /api/dashboard/ask-david` → `dashboard_ask_david()`
   (`dashboard/backend/main.py:7709`). After deterministic reads and the zero-model command
   fast-path, it runs David's turn: `_execute_named_profile_consultation("David", "david", text,
   request_id)` (`main.py:4272`, called at `main.py:7769`).
2. **David's turn executes** via `_run_hermes_message(..., launcher=HERMES_COORDINATOR,
   profile="david", ...)` (`main.py:4324`), which shells out to
   `tools/aos-hermes-coordinator.sh --profile david ... --oneshot` (`main.py:3963-3981`,
   `tools/aos-hermes-coordinator.sh:158-160`).
3. **David's reply is parsed** for the handoff by `_david_execution_handoff()`
   (`main.py:4635`) — it requires the literal `execution_handoff` key in a JSON object found
   anywhere in the reply text; no tool call is required to produce it.
4. **If found**, `_hermes_objective_from_handoff()` (`main.py:4667`) calls the existing
   `hermes_message()` endpoint function (`main.py:12719`) with `force_objective=True` — the exact
   same objective-creation path the dashboard already uses for any operator-typed objective.
5. **Decomposition** happens on **Operating Hermes = the `aos-orchestrator` Hermes profile**:
   `hermes_message()` calls `_run_hermes_message(direct_context)` with no profile override, and
   `_run_hermes_message`'s default is `profile: str = "aos-orchestrator"` (`main.py:3936`). This is
   confirmed independently by `tools/aos-hermes-coordinator.sh:8` (`profile="aos-orchestrator"` is
   the script's own default) and by the case statement at line 84 that only accepts
   `aos-orchestrator|aos-revenue|aos-marketing|aos-delivery|aos-ops|david`.
6. **Queue item creation:** the decomposition's chain proposal is normalized
   (`_normalize_chain_proposal`, `main.py:4709`) and turned into a real parent + child queue
   objective by `_create_executive_objective()` (`main.py:4840`) — `owner_type="workflow"`,
   `owner="hermes"` on the parent; each child starts `status="agent_todo"` (first step) or
   `"inbox"` (later steps), tagged `async_dispatch,executive_objective_child,hermes_chain`.
7. **Dispatch:** `_accept_async_queue_runner(children[0])` (`main.py:12102`) starts
   `tools/aos-orchestration-runner.py --dispatch-item <id>` as a detached subprocess if no
   recurring runner is already live (`_queue_runner_status` checks `logs/runtime/runner.pid`
   against the `aos-runner.service` systemd unit's own process). The runner's
   `dispatch_via_executor()` (`tools/aos-orchestration-runner.py:226`) ultimately calls
   `dispatch_via_backend()` (`:170`), which POSTs to `/api/queue/items/{item_id}/run`.
8. **Execution:** `run_queue_item()` (`main.py:10055`) claims the item, determines the owner via
   `_queue_worker_owner()` (`main.py:8976`), and — for `owner == "hermes"` — runs the worker turn
   with `_run_hermes_message(..., role="implementer", ...)` at its default profile
   `"aos-orchestrator"` (`main.py:9093-9108`). Department-owned steps (`revenue` / `marketing` /
   `delivery` / `operations`) instead route to that department's own Hermes profile
   (`main.py:9110-9126`).
9. **Review:** because `_create_executive_objective` hardcodes `review="model"` on every child
   (`main.py:4899`), `_queue_review_required()` (`main.py:9220`) is always true for a
   David-handoff-originated item, so a further Hermes review pass
   (`_queue_run_hermes_review`) runs after every worker attempt, on the same profile resolution as
   step 8.

David never touches the queue directly at any point in this chain — every write happens through
`hermes_message()` / `_create_executive_objective()` / the queue tool's own `claim_item` /
`attach_receipt` / `release_item`, exactly as `rules/david_execution_handoff.md` describes.

### A2. Did narrowing David break it?

Preimages compared (`/home/liam/ttros_backups/…`) against the live files:

| Change | What changed (diffed) | Does the handoff path depend on it? |
|---|---|---|
| **T3** (native tools) | `david/config.yaml` gained `agent.disabled_toolsets: [browser, web, vision, tts, file, skills, terminal, code_execution, delegation]` (comparing `david_config.yaml.PREIMAGE_20260908T044915Z` to current) | No. The handoff is plain-text JSON in David's reply; none of the disabled toolsets are needed to produce it. |
| **T4** (queue MCP removed) | `mcp_servers.queue` (`tools/queue_mcp.py`) deleted from `david/config.yaml` (`stepT4_2026-09-10/…PREIMAGE_pre-item1…` vs `…FINAL_postT4item1…`) | No — and this is the *correct* state per the contract ("David never creates, structures, or manages queue items"). Queue writes happen only in Orchestration Hermes's own code path (A1 step 6), never from David's session. |
| **T6** (session_search + brain resources/prompts) | `disabled_toolsets` gained `session_search`; `mcp_servers.brain.tools: {resources: false, prompts: false}` added (`stepT6_2026-09-10/david_config.yaml.PREIMAGE` vs current) | No. Neither setting is read by `_david_execution_handoff()`; they affect what David can look up, not whether it can emit the JSON block. |
| **T7 gate** | `hooks/context_assembler_hook.py` gained the `TTROS_DAVID_TEST_TURN` env-sentinel gate: when set, it suppresses the thread/journal write for that turn (`stepT7_2026-09-10/context_assembler_hook.py.PREIMAGE` vs current, lines ~38-50, ~199-225) | No — orthogonal. It only silences the *journal write* for turns explicitly marked as test/harness turns; it does not touch the handoff parser or the queue path. It matters for Part A6 below. |
| **T8-BCD `open_note`** | `tools/brain_memory_mcp.py`'s `open_note()` gained an optional `query` param for a bounded passage excerpt, plus raw intake-record support (`stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE` vs current) | No — a read-tool improvement on the `brain` MCP server, unrelated to queue/handoff creation. |

**Conclusion:** none of the five narrowing changes touch any function on the handoff→queue→dispatch
chain traced in A1. The narrowing affects what David can *see*, never what David can *do* with the
one channel (the JSON block in its reply) the contract actually uses.

### A3. Execution profiles

Coordinator-addressable profiles, from `tools/aos-hermes-coordinator.sh:84-91`:
`aos-orchestrator`, `aos-revenue`, `aos-marketing`, `aos-delivery`, `aos-ops`, `david`.
(`operator-lean` and `source-intake-semantic` are reached by other launchers, not this
coordinator.)

| Profile | `mcp_servers` | `agent.disabled_toolsets` override | `agent.max_turns` | `tools.tool_search` override | config.yaml mtime |
|---|---|---|---|---|---|
| aos-orchestrator | `brain` only | none (inherits global `[]`) | 150 (explicit) | none (global default: `enabled: auto`) | 2026-09-09 14:13:48 |
| aos-revenue | `brain` only | none | none set → inherits global 150 | none | 2026-09-09 14:13:48 |
| aos-marketing | `brain` only | none | none set → inherits global 150 | none | 2026-09-09 14:13:49 |
| aos-delivery | `brain` only | none | none set → inherits global 150 | none | 2026-09-09 14:13:49 |
| aos-ops | `brain` only | none | none set → inherits global 150 | none | 2026-09-09 14:13:50 |
| david | `brain` only | `browser, web, vision, tts, file, skills, terminal, code_execution, delegation, session_search` | 150 (explicit) | none | 2026-09-10 16:34:51 |

No profile has ever carried a `queue` MCP server since T4; only `david`'s preimage from before T4
did. `aos-orchestrator` is the only profile with a `platform_toolsets` override (adds
`computer_use`, `cronjob` to the global `cli` list).

Every profile's `config.yaml` mtime is after 2026-09-08. The five worker/orchestrator files
cluster within ~2 seconds of each other on 2026-09-09 14:13 PDT — consistent with a bulk rewrite
(most likely the Step 9 Hermes version upgrade touching every profile's config), but **no preimage
exists for these five files** (only `david`'s has the documented T3/T4/T6/T7/T8 preimages), so this
is reported as an mtime fact, not a content diff — I cannot say what specifically changed in the
other five beyond "something did, on 2026-09-09."

### A4. Composio

- **Not wired into any Hermes profile.** Confirmed by A3's table — every coordinator-addressable
  profile's `mcp_servers` contains only `brain`.
- **Wired at the dashboard backend / system Python layer**, in `dashboard/backend/main.py`:
  `_run_agentmail_composio_send()` (`:2409`), `/api/composio/connections` (`:3696`),
  `_run_composio_adapter()` (`:12518`), `/api/connectors/composio/action` (`:12880`),
  `/api/connectors/composio/refresh` (`:12932`) — all of these shell out to the `composio` CLI or
  to `connectors/composio_access_adapter.py` using `COMPOSIO_PATH` (`:757`, includes
  `/home/liam/.composio`). This matches the prompt's own note that Gmail capture uses
  `/home/liam/.composio` on system Python.
- **`connectors/composio_access_adapter.py`, `connectors/composio_tool_registry.json`, and the
  other Composio-named files under `connectors/` are inside the protected directory.** Per the
  permission header I did not open, diff, or read their contents — only their names (visible from
  file listing/`main.py` references) and the calling code in `main.py` were examined. I am
  stopping on the question of *what* those files do internally, as the header requires.
- Gmail draft capture (`connectors/gmail_draft_adapter.py`, `connectors/gmail_draft_policy.py`) is
  also under the protected directory and was not opened.

### A5. The two aos-orchestrator failures

From `/home/liam/.hermes/profiles/aos-orchestrator/state.db`, full session rows:

**Session `20260909_004350_d1ed06`** (started 2026-09-09 00:43:53.968 PDT):
`source="tool"`, `cwd=None`, `model_config={"max_iterations": 1, "reasoning_config":
{"effort":"medium"}}`, `message_count=0`, `tool_call_count=0`, `api_call_count=0`,
`end_reason="cli_close"`, duration ≈0.3s.

**Session `20260909_135449_e27b0f`** (started 2026-09-09 13:54:50.971 PDT):
`source="cli"`, `cwd="/tmp"`, `model_config={"max_iterations": 9223372036854775807,
"yolo_mode": true}`, `message_count=0`, `tool_call_count=0`, `api_call_count=0`,
`end_reason="agent_close"`, duration ≈0.07s.

Attribution attempted:
- **Logs do not survive.** `journalctl --user --list-boots` shows exactly one boot, starting
  2026-09-10 23:06:20 PDT — the machine rebooted since 09-09, and no journal history from before
  that boot exists for `aos-backend.service` / `aos-runner.service`. `logs/runtime/backend.log`
  and `runner.log` in the repo are stale (last modified 2026-08-10); nothing in `logs/` was
  written in either time window.
- **No context-assembly file exists for either session** in `queue/context_assemblies/` (checked
  both windows). Every genuine dashboard-driven Hermes call (David's turn, decomposition,
  worker, review) writes a `hermes-*.json` context assembly first (A1, step 2). The absence for
  both sessions means neither was launched through the `dashboard_ask_david` → `hermes_message` →
  `run_queue_item` chain traced in A1.
- **`async_delegations` is empty in every profile's `state.db`** that has the table (checked
  `david`, `aos-orchestrator`, `operator-lean`, `source-intake-semantic`; the four department
  profiles have no such table). So neither session is attributable to Hermes's own delegation/
  subagent tool.
- **Session 1** (`source="tool"`, `cwd=None`, bounded `max_iterations=1`) started within ~4-10
  seconds of file writes in `scripts/validation_a_runs/blind_run/` (`call_counter.json` at
  00:43:49.375, `phase2_rehearsal_plan.md` at 00:43:43.728, both 2026-09-09 PDT) — a Validation A
  / B6-leak-scorer detector rehearsal that was active in the same minute. That rehearsal's own
  plan document contains no reference to `aos-orchestrator`, so this is reported as a **temporal
  correlation only, not a proven cause** — I found no direct evidence tying that rehearsal script
  to this specific Hermes session.
- **Session 2** (`source="cli"`, `cwd="/tmp"`, uncapped `max_iterations`, `yolo_mode:true`) does
  not match how the production coordinator invokes Hermes: `tools/aos-hermes-coordinator.sh`
  always `cd`s to `$AOS_ROOT` before calling `hermes -p ...` and never sets `yolo_mode`
  (`main.py:1282`, `aos-hermes-coordinator.sh:158-160`). `cwd="/tmp"` with `yolo_mode` set is most
  consistent with a manual, ad hoc `hermes -p aos-orchestrator` invocation typed by hand from a
  shell sitting in `/tmp` — not a dispatch through the dashboard/runner path.
- **STEP U fail-closed guard:** `hooks/context_assembler_hook.py:main()` (`:239-251`) — if
  `evaluate()` raises for any reason, the hook returns `{"error": ...}` with **no context
  marker**, and its own comment states: *"the scoped Hermes runtime has a matching fail-closed
  marker check; returning no marker prevents a model call instead of degrading."* Both failed
  sessions show exactly the fingerprint this guard is designed to produce — zero messages, zero
  tool calls, zero API calls, immediate `cli_close`/`agent_close`. **This is consistent with, but
  not independently proven for, these two sessions** — no surviving log captures the hook's
  stderr or exit code for either invocation, so I cannot confirm the hook actually raised rather
  than some other zero-call abort path. State explicitly: what this licenses is "the observed
  shape matches the guard's designed behavior"; it does not license "the guard definitely fired
  here" as a proven fact.

### A6. Side effects of a test item

- **No Telegram notification for a non-Telegram-sourced item.** Both outbound Telegram paths are
  gated on `item.source == "telegram"`: `_telegram_reply_on_close()` (`main.py:3311-3314`, checked
  at close) and `_notify_queue_completion()` (`main.py:9711-9723`, checked at async-runner
  completion). `_create_executive_objective()` sets `source="dashboard/hermes_message"` by default
  on every item it creates (`main.py:4844`), never `"telegram"`, for anything driven through the
  `ask-david` endpoint. No other outbound channel (email/Slack/Discord/webhook) appears anywhere
  in the queue-completion code path — searched and found none.
- **No "Needs Me" entry for a plain single-step local command.** A test item has no `on_complete`
  gate and no `external/outbound/send/client_facing/payment` tag, so `run_queue_item`'s gate logic
  (`main.py:10151-10160`) resolves `passing_status = "done"` on a PASS review, not
  `human_review`/`needs_input` — it would only surface in "Needs Me" if it failed review.
- **`TTROS_DAVID_TEST_TURN=1` cannot reach a David turn driven through the real production entry
  point.** `_run_wsl_supervised()` (`main.py:1279-1330`) spawns `bash -lc` via
  `subprocess.Popen(...)` **without an `env=` argument**, so the child inherits the environment of
  whatever process is already running `aos-backend.service` (a live systemd unit). This session
  has no authorized way to inject an env var into that already-running service without a restart,
  and restarts are explicitly out of scope for this step. **Consequence: driving Part B through
  the real `/api/dashboard/ask-david` endpoint will leave a real, non-test-marked David turn in
  `sessions/*.md` / `thread_david.md`** — the T7 gate will not suppress it. This directly
  determines the Part B plan below (acceptance criterion 5's fallback path, not its primary path).
- **Runaway-turn stop mechanism exists and is independent of Hermes's own `max_turns`.**
  `HERMES_EXECUTION_TIMEOUT_SECONDS` defaults to 600s (`main.py:784-786`, override via
  `AOS_HERMES_TIMEOUT_SECONDS`). `_run_wsl_supervised` calls `process.communicate(timeout=...)`
  and on `TimeoutExpired` calls `_terminate_process_group()` (`main.py:1300-1307`), which kills the
  whole process group (the subprocess was started with `start_new_session=True`,
  `main.py:1289`, enabling `killpg`). This is a wall-clock kill switch that fires regardless of
  what `agent.max_turns` or `model_config.max_iterations` say inside Hermes itself.

---

## Part B — not run

Part A found the path intact, no external-message risk, and a working runaway-stop mechanism — the
three preconditions this step names for running Part B. I did not run it anyway, for a fourth
reason the step didn't ask me to check but which Part A's own trace surfaced:

**The real production path costs a minimum of four Hermes model invocations for one end-to-end
handoff, not two.** From A1: (1) David's decision turn, (2) Operating Hermes's decomposition turn
(`hermes_message()` → `_run_hermes_message`, profile `aos-orchestrator`, triggered synchronously
inside the same `ask-david` request before it even returns), (3) the worker execution turn
(`run_queue_item`'s `owner=="hermes"` branch, another `aos-orchestrator` invocation, dispatched
asynchronously right after), and (4) a mandatory Hermes review turn — `_create_executive_objective`
hardcodes `review="model"` on every child it creates (`main.py:4899`), and `_queue_review_required`
(`main.py:9220-9229`) returns `True` whenever `item.review == "model"`, with no scope-hint-based
exception. There is no way to reach "one execution-profile turn" for a David-handoff-originated
item through this entry point; decomposition and review are not optional side paths, they are the
same code every operator-typed objective goes through.

Per the evidence-discipline rule this repo already states — *"a budget stated only in a prompt is
not a budget... needing more calls than declared is a finding to report, never a number to quietly
raise mid-run"* — I stopped before spending a second call rather than silently running to four. I
did not touch `/api/dashboard/ask-david`, did not create a queue item, and made zero model calls in
this step.

**What this licenses:** the declared 2-call budget for Part B does not match the code-verified
shape of the only path Part B is allowed to exercise ("the same entry point production uses"). It
does not license any claim about whether the live run would actually succeed — that remains
untested. **What it does not license:** a claim that the handoff is broken — A1-A6 show the
opposite.

**If Liam wants this actually run:** a follow-up step declaring at least 4 invocations (or
explicitly accepting a partial proof — e.g., stopping after confirming the queue item was created
by David's handoff and only asserting the decomposition call, leaving the worker/review turns
unexercised) would close this. Either way, per A6, the run should be preceded by a decision on
whether the resulting David turn is acceptable as a permanent entry in `sessions/*.md`/
`thread_david.md` (it will be, since `TTROS_DAVID_TEST_TURN` cannot reach it without a service
restart) or whether it should be removed afterward through the gated `write_transaction` path
T8-A used, with a preimage first, as the step's own Authorized section anticipates.

---

## Part C — nothing to repair

Part A found the handoff path intact and unbroken by David's narrowing. There is no code defect to
propose a repair for. The one gap surfaced — the Part B budget mismatch (A6 last bullet, and the
Part B section above) — is a step-calibration issue, not a bug in the running system, so no
rollback/validation plan applies. Not applied; nothing was proposed to apply.

---

## What this licenses / does not license

**Licenses:**
- David's `execution_handoff` mechanism reaches Operating Hermes (`aos-orchestrator`) and the real
  queue/runner/backend spine today, in code, unmodified by any narrowing step to date.
- None of T3/T4/T6/T7/T8-BCD removed anything the handoff path uses.
- Composio has no Hermes-profile footprint; it is a dashboard-backend/system-Python integration
  only, calling into the protected `connectors/` adapter.
- A test item driven through this path would not send any external message and would not surface
  in "Needs Me" unless it failed review.
- A runaway turn has a working, Hermes-independent 600s kill switch.
- `api_call_count` undercounts real model round trips by at least one when a turn-limit notice
  triggers a grace continuation (Part 0).

**Does not license:**
- Any claim that a live end-to-end handoff actually succeeds in production — Part B was not run.
- Any confirmed cause for the two 2026-09-09 aos-orchestrator failures — attribution is
  circumstantial (session-row shape, adjacent file-write timing) with no surviving log to close
  the gap; the STEP U fail-closed guard is consistent with, but not proven as, the mechanism.
- Any statement about what the five worker/orchestrator profile configs looked like before
  2026-09-09 14:13 PDT — no preimage exists for them.
- Any claim about the internal behavior of `connectors/composio_access_adapter.py` or the other
  Composio files under `connectors/` — not opened, per the protected-boundary rule.

## Invocations used vs. declared

Declared: 2 (Part B only). **Used: 0.** Parts 0, A, and C are model-call-free as designed; Part B
was not run for the budget-mismatch reason stated above.

## Note on this session's own conduct

One boundary was crossed and is disclosed above under the Composio verdict: an unscoped
`grep -rl composio .` walked into `connectors/` before I excluded it. No protected content was
displayed or acted on (only filenames came back), and every subsequent search excluded
`connectors/` and `workspaces/north_shore_sales_coach/`.
