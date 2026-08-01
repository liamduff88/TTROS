# DECISIONS.md — log of decisions that change system behavior
> One entry per behavior-affecting change. Newest first.

## 2026-08-01 — Operator lean has one explicit executive escalation tool

The operator-only MCP surface gains one guarded `escalate_to_executive` call
for business-wide opinion, synthesis, and priority judgment. It forwards the
already assembled current message and rolling window into one per-invocation
`aos-orchestrator` run, whose existing launcher supplies the executive brief.
The call echoes visibly, cannot recur or become sticky, cannot share an inbound
turn with task creation, and writes a receipt plus exact Hermes usage evidence
without creating queue work or changing the global/default profile.

Files touched: live `hermes.py`, `queue/profiles/operator-lean.md`,
`tools/aos-hermes-operator-lean.sh`, `tools/operator_lean_mcp.py`,
`tools/operator_lean_oneshot.py`, focused routing tests, and
`decisions/DECISIONS.md`.

## 2026-08-01 — Queue provenance outranks receipts; brief unknowns and pytest boundaries are explicit

Per-message Gmail proposals are identified by the exact capture source
`capture/gmail-live-read-only`, not by ID range, and may be cancelled when they
are metadata-only and have no queue artifact. Receipt existence is not business
value evidence. The executive brief now counts genuine conflicts separately
from notes whose freshness metadata cannot be parsed, and the default pytest
configuration structurally excludes the North Shore workspace and Telegram
bridge directory from collection.

Files touched: `queue/work_items.jsonl`, archive snapshot,
`tools/aos_executive_brief.py`, `tests/test_aos_executive_brief.py`,
`pytest.ini`, generated executive artifacts, closeout receipt, and
`decisions/DECISIONS.md`.

## 2026-08-01 — Gmail capture routes runs to evidence plus one review digest

The existing read-only Gmail poll keeps its provider scope, schedule,
authentication, cursor, deduplication, isolation, and no-mutation boundaries,
but no longer treats each captured message as queue work. Every captured row
gets a private, dated, content-free record under `capture/gmail/`; a material
poll creates at most one idempotent `human_review` digest linking those records,
and an empty/non-material poll creates no item. Ordinary search excludes the
private evidence tree and continues to consume only the existing typed capture
metadata projection.

The executive brief now reads every Markdown note below the canonical
`memory/` and `operating_context/` roots, reports reads/skips and UNKNOWN
freshness states, detects semantic contradictions, stale stamps, and met
deterministic Revisit conditions, shows informative bounded Decisions rows,
and selects recent plus genuinely stale material Open items while excluding
dead fixtures and stale immaterial rows.

Files touched: `.gitignore`, `capture/README.md`, `tools/aos_capture.py`,
`tools/aos_capture_live.py`, `tools/aos_indexer.py`,
`tools/aos_executive_brief.py`, focused tests, generated executive artifacts,
archive snapshot/summary, cancellation receipt, and `decisions/DECISIONS.md`.

## 2026-07-31 — Existing executive paths receive one bounded live brief

One deterministic local refresh projects the existing queue, receipts, run and
prospect ledgers, metadata-only capture proposals, approved local notes, and
canonical indexed Business Brain notes into two atomic artifacts. The lean
operator receives only the one-line header; `aos-orchestrator` receives the full
brief before reasoning. Failed refreshes retain the last good brief and mark its
header stale. Neither path creates queue work, auto-escalates, calls a model,
adds a scheduler, or replaces scoped Business Brain retrieval.

Files touched: `tools/aos_executive_brief.py`,
`tests/test_aos_executive_brief.py`, `context/EXECUTIVE_BRIEF.md`,
`context/EXECUTIVE_HEADER.txt`, `tools/aos-hermes-operator-lean.sh`,
`tools/aos-hermes-coordinator.sh`, `decisions/DECISIONS.md`.

## 2026-07-31 — Linux runtime adopts one canonical orphaned Vite process

`start` and `status` now identify exactly one Vite process rooted in the live
frontend with port 3010 and adopt/report it, matching the existing runner
adoption contract. Multiple matches fail as ambiguous. This prevents a stale
npm PID file from making restart report `frontend=stopped` while the real live
frontend is healthy and holding the port.

Files touched: `tools/aos-linux-runtime.sh`,
`tests/test_aos_dashboard_cleanup.py`, `decisions/DECISIONS.md`.

## 2026-07-31 — Gmail capture hydrates bounded Composio large-result artifacts

The current Composio CLI stores sufficiently large successful tool results in
its local `/tmp/composio` artifact area and returns a pointer envelope. The
read-only Gmail capture executor now hydrates that envelope in-process after
absolute-path, containment, non-symlink, regular-file, size, UTF-8, JSON, and
object-shape checks. Provider/message identifiers remain out of poll receipts
and operator status output. No Gmail mutation or new action was added.

Files touched: `tools/aos_capture_live.py`,
`tests/test_aos_capture_live.py`, `decisions/DECISIONS.md`.

## 2026-07-31 — Search status exposes logical ingestion identity only

The deterministic index retains historical ingestion receipts unchanged, but
its operator-facing status response no longer returns absolute `source_path`
or `source_root` values. The logical indexed path, source, status, timestamp,
and token evidence remain visible. This prevents a pre-migration receipt from
being presented as a current Windows runtime authority and avoids leaking host
filesystem details that are unnecessary for health assessment.

Files touched: `tools/aos_indexer.py`, `tests/test_aos_search.py`,
`decisions/DECISIONS.md`.

## 2026-07-31 — Activate proven internal gaps without new frameworks

The existing daily Windows task now invokes the existing Linux backup script
against `/home/liam/agentic-os-live` and a Linux-native backup root; protected
client/bridge subtrees and `.env` files are excluded. The existing Graphify
document service rebuilt its derived 29-source Business Brain projection.

Queue `done` transitions now enforce the documented receipt-completeness
contract at the same `finalize_done()` point as token metering: a real receipt,
completion contract, validation note, and schema-valid lane/profile/model/token/
artifact record are required. Completed explicitly reviewed skill runs append
the existing skill-trust ledger. The other five protection specs execute at
their smallest real boundaries: Hermes native `pre_tool_call`, scoped Business
Brain retrieval/completion, and the shared Composio mutation adapter.

The shared Hermes coordinator launcher accepts only the five existing `aos-*`
profiles and the dashboard passes the routed profile with native `-p` per
invocation. Department-scoped authentication was repaired by reusing the
working orchestrator auth source; all four departments and orchestrator-to-
department delegation passed live proofs without `default` fallback. The
active/default Hermes profile and default config were not changed.

Root `prospector.py` is a thin operational entry point over the existing
`prospecting_daily_run` engine, canonical ledgers/review cards, scoped Business
Brain retrieval, and Gmail draft-only behavior. No second queue, CRM,
prospecting engine, scheduler, approval system, or connector stack was added.

Files touched: backup scripts, queue done lifecycle/schema/tests, hook runtime
and docs, Hermes launcher/profile docs/routing tests, external-action adapter,
prospecting entry point/tests/proofs, dashboard human-review receipt generation,
`docs/ACTIVATION_STATUS.md`, and `decisions/DECISIONS.md`.

## 2026-07-31 — Memory Board edits canonical Business Brain Markdown directly

Memory Board rows now open the full registry-approved global Business Brain
note and expose the same manual edit/save interaction used by the Skills Board.
Saves replace the exact canonical Markdown file with optimistic revision and
post-write verification, reject traversal, backup, unapproved, non-Markdown,
and vault-escaping targets, and report the existing per-file search refresh
result. Direct Liam edits do not enter the semantic promotion/review path;
Graphify receives no new synchronization mechanism.

Files touched: `dashboard/backend/main.py`,
`dashboard/backend/test_composio_hermes.py`, `dashboard/frontend/src/api.js`,
`dashboard/frontend/src/views/DashboardV1.jsx`, focused Memory Board tests and
browser-proof artifacts, `decisions/DECISIONS.md`.

## 2026-07-28 — Operator-lean retrieves scoped Business Brain notes on demand

Olmec still sends generic conversation through one lean Hermes call without
loading the Business Brain. Two narrow conversational question gates now use
the existing default-deny `ScopedBrainLoader` pointer route: TTR/company
questions receive company, offers, and positioning notes; client-acquisition
focus questions receive current priorities, sales/revenue, and the prospecting
rotation plan. At most 6,000 bytes of those scoped notes enter the dynamic user
prompt, with exact retrieval provenance returned in the closeout. Execution,
deterministic reads, queue behavior, recent-turn bounds, and the six-tool fixed
preamble are unchanged. The existing `create_task.worker` schema now advertises
the same six worker names already enforced at runtime, removing model ambiguity
without changing the accepted worker set.

Files touched: `dashboard/backend/main.py`,
`queue/profiles/operator-lean.md`,
`tools/operator_lean_mcp.py`,
`tests/test_telegram_conversational_routing.py`,
`proofs/operator-lean-brain-context/2026-07-28/FOCUSED_PROOF.md`,
`decisions/DECISIONS.md`.

## 2026-07-28 — Telegram preserves Hermes operator-lean direct replies

The Telegram bridge now treats the backend's explicit `direct_reply` flag as a
delivery contract. Substantive operator-lean conversation is sent unchanged
instead of being compacted into the queue closeout format. Queue intake and
completion formatting are unchanged, and a Hermes failure remains a direct
failure reply with no inferred task creation. The unverified-creation guard is
anchored to affirmative creation closeouts, so ordinary discussion containing
words such as "created" and "work" cannot be mistaken for a queue claim.

Files touched: `connectors/telegram_bridge/telegram_bridge.py`,
`dashboard/backend/main.py`, `tests/test_telegram_conversational_routing.py`,
`decisions/DECISIONS.md`.

## 2026-07-28 — Olmec falls through to Hermes operator-lean

Olmec is the interface. Slash commands and one frozen literal table remain
deterministic zero-token paths; natural-language variants are intentionally not
added as semantic router rules. Every other inbound message uses one bounded
Hermes `operator-lean` turn. That profile has no skills, memory, Business Brain,
delegation, orchestration, or built-in toolsets and exposes only five local
read tools plus `create_task`; the mutation tool is single-call per inbound.

Conversation and reads never queue. Clear execution creates at most one tracked
item, with Codex reserved for repository/code-file changes. `/work` overrides
remain deterministic. `size: small` Codex work uses a dedicated prompt that
contains the stripped operator instruction once, preserves a fresh ephemeral
session, and omits full supervisor/artifact/reviewer boilerplate. The full
Codex template remains unchanged for substantive work.

The literal `What tasks are open?` now uses the existing local open-task reader
with one canonical ID/title/state/owner row, removing duplicate metadata.
Existing item-bound approval/rejection/clarification protocols, queue/receipt
integrity, delivery idempotency, and specialist workers remain unchanged.

The TTROS oneshot wrapper now calls Hermes' own MCP discovery synchronously in
the same process and validates the exact six-name snapshot before importing the
Hermes oneshot runner. Missing or extra tools return `TOOL_UNAVAILABLE` before
agent construction or any model call. Backend closeout also replaces an
unverified positive queue claim with an explicit no-task-created error.

The `operator-lean` profile alone disables Hermes' generic tool-completion,
parallel-call, GPT enforcement, and environment-probe prompt blocks and replaces
the verbose CLI hint with one short plain-text instruction. Its SOUL retains the
complete queue contract. The live post-discovery prompt is 719 exact
`o200k_base` system tokens plus 441 for all six schemas: 1,160 total.
Global/default Hermes configuration is unchanged.

Files touched: `connectors/telegram_bridge/README.md`,
`dashboard/backend/main.py`, `queue/command_routes.json`,
`queue/lane_profiles.json`, `queue/model_routes.json`, `queue/profiles/`,
`queue/templates/`, `tools/aos-hermes-operator-lean.sh`,
`tools/operator_lean_mcp.py`, `tools/operator_lean_oneshot.py`, focused routing
tests, `requirements.txt`, `decisions/DECISIONS.md`, and the local
`operator-lean` profile config only.

## 2026-07-23 — Fourth _run_wsl_supervised test gap found during verification

Post-commit verification of the previous entry's 3-test fix ran the full
`test_composio_hermes.py` file standalone (not just the 3 named tests) and
found `test_queue_run_receipt_and_token_ledger_include_route_metadata_without_prompt`
newly failing — same root cause (patched `_run_wsl`, code now calls
`_run_wsl_supervised` unconditionally for the department/Hermes path), just
missed in the original grep. Left unmocked, it fell through to a real
`subprocess.Popen` invoking the real `aos-hermes-coordinator.sh`, which is
why it ran 65s instead of milliseconds and returned a non-deterministic
result. Fixed the same way as the other 3: patch `_run_wsl_supervised`
instead of `_run_wsl`, with a matching `on_process_start=None` kwarg on the
fake. Confirmed deterministic with 3 back-to-back full-file runs (207/207
passed each, ~34s each, down from the earlier 60s+ real-subprocess runs).

Files touched: `dashboard/backend/test_composio_hermes.py`.

## 2026-07-23 — Reconciled 3 tests with the already-decided supervised/async-ack behavior

Running the suite after the small-task fast-path work surfaced 3 failures that
predated it. Investigated each rather than leaving them ambient:

1. **`test_queue_run_uses_prompt_files_and_redacted_token_task` and
   `test_explicit_model_provider_route_builds_hermes_flags`** (both in
   `test_composio_hermes.py`) patched `_run_wsl` and asserted on commands
   captured through it. `_run_wsl_prompt_command` and `_run_hermes_message`
   had already been changed (uncommitted, predating this session) to always
   call `_run_wsl_supervised` instead of falling back to unsupervised
   `_run_wsl` when no `startup_timeout` is given. That change is intentional:
   it matches this same day's "Olmec Telegram work is asynchronous and
   delivery-idempotent" entry ("Hermes work is a fresh supervised one-shot
   with a 600-second ceiling"), and it fixes a real latent bug — the
   department/Hermes worker path passes `on_process_start=register_runtime`
   into `_run_wsl_prompt_command`, but the old unsupervised `_run_wsl` branch
   doesn't accept that argument, so worker-runtime registration for
   stuck-job recovery was silently never firing on that path. **Fix-forward,
   not revert**: updated both tests to patch `_run_wsl_supervised` (with a
   matching `on_process_start=None` kwarg on the fake) instead of `_run_wsl`.
2. **`test_dashboard_notification_and_approval_paths_use_title_first_helpers`**
   (`test_aos_orchestration.py`) asserted the literal call site
   `running_notification = _notify_queue_running(item_id)` exists. That call
   site had already been deliberately removed (uncommitted, predating this
   session) and replaced with `running_notification = None` plus a comment,
   because — per the same Telegram entry — "the intake closeout is the sole
   acknowledgement and the existing idempotent completion notification
   remains the sole final message/receipt path"; a second running-notice
   would violate that. **Fix-forward, not revert**: updated the assertion to
   check for the new `running_notification = None` line and its explanatory
   comment instead of the removed call site. `_notify_queue_running` itself
   is left defined (used by other recovery paths) — only its call site here
   changed.

All three were deliberate, already-reasoned changes with no corresponding
test update yet, not accidental regressions or code to revert.

Files touched: `dashboard/backend/test_composio_hermes.py`,
`tests/test_aos_orchestration.py`.

Tests: full targeted suite (`tests.test_aos_queue`, `tests.test_aos_paths`,
`tests/test_outreach_handoff.py`, `dashboard.backend.test_composio_hermes`,
`tests.test_workflow_prompt_templates`, `tests.test_aos_orchestration`,
`tests.test_aos_codex_policy`) — 337 passed, 0 failed.

## 2026-07-23 — Opt-in small-task fast path for the Claude queue worker

Diagnosed why a trivial one-file `claude`-owned queue item was costing ~165k
fresh input tokens and ~34 API calls: every item, regardless of size, ran
through a fresh `claude -p --dangerously-skip-permissions` session that
CLAUDE.md's "before writing code" section forces to re-read README.md,
context/PATHS.md, ROT.md, rules/never.md, and the Business Brain index before
touching anything, then (when `review: model`) paid for a second, independent
full agent session to review the first one's output — with no continuation
between attempts.

Added an opt-in `size: small` queue-item field (default off; existing items
unaffected):
- `_queue_render_prompt` now selects `queue/templates/claude_task_small.prompt.md`
  for `owner=claude` items flagged `size: small`. The template tells the
  worker to skip the mandated repo-orientation reads and inlines
  `rules/never.md` via a live `<NEVER_RULES>` substitution at render time
  (never a pasted static copy, so it can't drift from the source file).
- `_queue_review_required()` lets a `size: small` item skip the Hermes/
  `aos-orchestrator` review pass, but only when the worker's own reported
  output shows a test referenced in its `definition_of_done`/`context`
  genuinely ran and passed (test path present, a pass marker present, no
  fail/error/traceback marker) — a bare reference is not enough, and an
  explicit `review: model` always still forces the review pass regardless of
  size.
- `_queue_fast_path_hint_line()` adds a `Fast-path hint:` line to the run
  receipt for items that were *not* flagged `size: small` but whose worker
  output would have qualified — visibility only, no behavior change.
- Removed the duplicate "PERMISSION MODE — SCOPED LOCAL TASK APPROVED" wrap
  in `/home/liam/agentic-os/hermes/hermes.py` (outside this repo, backed up
  alongside as `hermes.py.bak-2026-07-23`): it now passes an already-wrapped
  queue prompt through verbatim instead of nesting a second copy of the same
  header inside it. Bare ad-hoc tasks (e.g. `/api/wsl/claude`) still get
  wrapped as before.

Files touched: `dashboard/backend/main.py`, `queue/templates/claude_task_small.prompt.md`
(new), `/home/liam/agentic-os/hermes/hermes.py` (external, backed up).

Tests: `tests.test_aos_queue`, `tests.test_aos_paths`,
`tests/test_outreach_handoff.py`, `dashboard.backend.test_composio_hermes`,
`tests.test_workflow_prompt_templates`, `tests.test_aos_orchestration`,
`tests.test_aos_codex_policy` — 329 passed. Three pre-existing failures
(2 in `test_composio_hermes.py` expecting `_run_wsl_prompt_command` to call
`_run_wsl`, 1 in `test_aos_orchestration.py` expecting a `_notify_queue_running`
call site) predate this change — confirmed by their locations sitting outside
every function this change touched — and were not introduced or fixed here.

## 2026-07-23 — Olmec Telegram work is asynchronous and delivery-idempotent

The canonical Telegram bridge keeps polling while agent intake runs on a
background thread. Each Telegram update supplies a durable delivery ID to the
existing queue, and only the first queue creation may start an on-demand
runner; replays reuse the item without launching another process. The intake
closeout is the sole acknowledgement and the existing idempotent completion
notification remains the sole final message/receipt path. Hermes work is a
fresh supervised one-shot with a 600-second ceiling, and lightweight status,
capture, identity, and help commands remain deterministic and token-free.

## 2026-07-23 — Outreach handoffs reuse the prospect ledger and review queue

V3.1 outreach handoffs validate and reconcile before activation, append typed
full snapshots to `queue/prospects.jsonl`, and create one typed
`human_review` work item per eligible prospect. Actual Liam-recorded events
alone advance `outreach_stage`; each send/action calculates at most one
business-day reminder, and every configured stop event cancels future copy.
Gmail remains draft-only, LinkedIn remains manual, and GoHighLevel is exposed
only as an idempotent dry-run projection embedded in the same prospect
snapshot. No second CRM, queue, scheduler, review system, receipt store, or
connector framework was added.

## 2026-07-20 — Carousel resource CTAs resolve deterministically to post links

`linkedin_carousel_from_md` now resolves controlled final-slide/caption
markers from optional structured resource metadata first, then from weighted
source/title/heading, carousel, caption, and link context. A confidence and
margin gate prevents unsupported specificity; ambiguous content uses the
neutral full-resource wording. The PDF points to the LinkedIn post without a
raw URL, while the caption carries the configured URL or an unmistakable
pre-post review placeholder. Resource type, action, copy, evidence, and
fallback state are stored in `post_package.json`; message-based CTAs are not an
active mode.

## 2026-07-20 — LinkedIn carousel packages use the existing PDF renderer

`linkedin_carousel_from_md` now calls a strict Playwright/Chromium carousel
profile in `workflows/pdf_branding`, producing one validated 8×10-inch PDF page
per Markdown slide plus the existing six-file review package. A4 report behavior
is preserved; carousel runs reject fallback/placeholder PDFs, overflow, blank or
duplicate pages, page-count drift, and source/caption mismatch. All LinkedIn
posting, upload, scheduling, messaging, and connection actions remain manual.

## 2026-07-20 — Timed-out Codex launches terminate as bounded process groups

Timed-out Codex launches terminate their full Linux process group with bounded
TERM, KILL, and output-collection phases, retain available usage reconciliation,
and surface an explicit timeout result.

## 2026-07-20 — Token component availability survives aggregation

Token source summaries retain known cached and reasoning totals while counting
unavailable components separately, allowing the dashboard to distinguish
complete zero, complete totals, partial totals, and unavailable values.

## 2026-07-20 — Telegram attachment identity is atomic and conflict-safe

Telegram attachment storage derives one atomic target from capture identity,
rejects byte-mismatched replays, preserves a concurrently completed companion
pair during rollback, and keeps legacy stamped captures discoverable.

## 2026-07-19 — Dashboard and Olmec share one raw Business Brain inbox

The persistent dashboard capture box and the existing Telegram bridge now use
one append-only writer rooted at `business_brain:inbox/source_notes/`.
Dashboard capture is separate from Cockpit command routing; Telegram capture is
explicit via `/inbox` or `/capture`, with forwarded content treated as an
unambiguous capture signal. Stable hashed replay identities prevent duplicates
without a new state store, raw captures remain outside queue, search, Graphify,
and promotion, and no capture automatically creates work. Telegram attachments
receive companion intake notes. Voice audio is retained; transcription remains
honestly unavailable unless a local Whisper-compatible argv adapter is
configured.

## 2026-07-19 — Codex work is fresh-session, artifact-backed, and cache-normalized

Every guarded Codex constructor now uses ephemeral `exec`, injects the scoped
permission plus 50% handoff contract, and requires one real `thread.started`
identity; implicit resume, persisted transcript inheritance, and synthetic
fallback session IDs are rejected. Hermes children and corrections therefore
run independently. Correction prompts contain bounded original task context,
essential repository references, a compact prior-result summary and artifact
paths, Hermes feedback, and acceptance criteria only. Raw JSONL/stderr is kept
in per-session artifacts and returned only as bounded tails.

Codex `input_tokens` is recorded as provider-total input. Fresh input is
derived by subtracting cached input, cache ratio uses fresh input as its
denominator, and cached input is neither added to total input nor charged at
the normal rate. The deterministic pricing path uses the configured cache-read
rate, records soft cache/context warnings, and weekly rollups expose the top
five cache-ratio sessions plus context-ceiling breaches. Legacy `input` remains
provider-total input and missing harness fields remain explicitly unavailable.

## 2026-07-18 — Telegram intent routing is deterministic only at confident boundaries

Natural-language Codex and Claude Code delegation now enters the existing queue/runner directly without invoking Hermes; structured queue, receipt, blocker, worker, completion, attempt, and token questions remain local reads with no queue or model work. Every other conversational or judgment-bearing request invokes native Hermes through a per-invocation `aos-orchestrator` profile, without mutating the sticky Hermes default. Explicit Codex-plus-review requests create bounded Codex children under Hermes coordination: Hermes reviews the initial result and at most two corrections, closes passing workflows without Liam review, and creates one Liam escalation after the third failed review with no fourth attempt. Human-review cards hydrate the substantive receipt and consolidated artifact, save optional notes without state changes, and reserve `done` exclusively for a confirmed explicit Approve action. Hermes and workbench sessions are metered separately using total/cached/calculated non-cached input labels; already-metered sessions are not aggregated a second time.

## 2026-07-18 — Bounded Codex context and opt-in model review

Codex launches now auto-compact at 75,000 tokens and receive standing tool-output bounds. Queue runs use deterministic proof by default; the existing Hermes reviewer runs only for `review: model` and sees only the final artifact or bounded closeout. Oversized Telegram `/work` intake persists one prompt file, merges its continuation into the same item, and adds `consider decomposing` to Needs Me metadata. Exact-or-unavailable usage counters and a configurable 75-turn Needs Me alert are additive to existing ledgers and receipts.

## 2026-07-18 — Queue workers outlive restartable control-plane processes

Tagged asynchronous work now launches through a detached per-item executor
using the dashboard backend virtualenv and a durable startup log. The executor
registers the exact worker PID plus Linux process-start identity before the
canonical `aos-claude` run, while heartbeat recovery refuses to reclaim a
stale-looking lease if that exact process remains live. The 7,800-second
execution timeout and wrapper permission contract are unchanged. Queue list
responses are compact with detail loaded only for the selected item; operator
surfaces use `AOS-ID — title`, preserve the last valid state after refresh
failures, and hide external handoff controls for internal work. Telegram
continuations that resemble an oversized split `/work` command fail closed
instead of creating a second natural-language item.

## 2026-07-18 — Claude queue execution and artifacts are Linux-root canonical

The installed Claude wrapper and backend worker now bind `AOS_ROOT`, process
cwd, artifact normalization, validation, hashing, receipts, and reviewer input
to `/home/liam/agentic-os-live`. Claude execution is capped at 7,800 seconds,
with separate startup, parent/grace, lease/heartbeat, reviewer, and local
finalization contracts. A claimed missing artifact still fails closed, while a
reviewer-only path-missing contradiction against an available canonical file is
overruled without a duplicate worker invocation. Hermes review consumes a
bounded copy of the worker's full closeout, not the operator-compacted summary,
so validation and artifact sections cannot disappear between worker and review.

## 2026-07-17 — Agentic OS Codex execution is unconditionally full access

Every active Agentic OS Codex subprocess now consumes one repository policy
that pins Liam, `/home/liam/agentic-os-live`, the authenticated local Codex
installation/home, `danger-full-access`, and approval policy `never`. Backend,
queue, runner, Telegram, dashboard, workflow, Hermes-owned queue delegation,
and local-launcher routes either converge on that constructor or show the same
fixed operator command. Alternate roots, users, missing binaries, and policy
defects fail closed without another installation, workspace, permission mode,
or interactive approval fallback. Existing third-party external-action gates
are unchanged.

## 2026-07-17 — Operator queue notifications are title-first

Telegram-facing queue messages and queue-list rows now present the actual task
title before the AOS ID, while retaining the ID as audit metadata. Queued,
running, needs-input, review, done, failed/recovered, receipt captions, and
multi-item pending lists use the shared title-plus-ID formatter and attach an
existing receipt document where the current Telegram bridge send path supports
it. The old ID remains internally available for idempotency and ledgers.

## 2026-07-17 — Telegram approvals bind to one correlated existing item

The unprotected `/api/wsl/hermes` intake now parses a bounded deterministic
approval family before substantive queue creation. A unique same-conversation
`needs_input` item resumes in place and a unique `human_review` item closes
through the existing local review contract; delivery replay reuses the durable
item-bound effect. Missing, ambiguous, external, or destructive targets return
bounded clarification and never become approval-shaped work items. Substantial
non-approval requests retain the asynchronous queue/runner path.

## 2026-07-17 — Gmail authority adds idempotent draft creation only

Agentic OS may create Gmail drafts without per-draft approval only through the
dedicated Composio adapter and exact live action `GMAIL_CREATE_EMAIL_DRAFT`.
The effect key is deterministic from work-item ID + prospect/message identity;
private recovery state is Git-ignored and search-excluded, while queue receipts
contain safe metadata only. Generic Gmail routing is executable read-only and
unconditionally rejects send, reply, forward, schedule-send, draft
update/delete, and message/label mutation. The canonical prospecting workflow
now creates at most one tailored draft per validated prospect and never falls
back to sending.

## 2026-07-17 — Telegram/Olmec substantive work uses the existing queue runner

`/api/wsl/hermes` now keeps only exact bounded queue-status/list reads inline;
all other operator work is filed once as a tagged `agent_todo` item and returns
its real ID immediately. The existing orchestration runner dispatches only
those tagged items through the existing queue run endpoint. Agent execution has
an independent 1,800-second default safety ceiling, while renewable 30-second
heartbeats and a 90-second lease distinguish healthy long work from abandoned
claims. Completion and failure retain the normal receipt, Needs Me, and
idempotent Telegram notification paths.

## 2026-07-13 — Graphify previews expose local graph interaction

The self-contained Graphify graph preview now supports node click and keyboard
selection with repository metadata and relationship highlighting, plus pointer
pan, wheel/button zoom, and view reset. The interaction remains inline and
dependency-free inside the existing provenance-bound artifact; the restrictive
`sandbox="allow-scripts"` iframe and no-network content-security policy are
unchanged.

## 2026-07-13 — Repo Ingest and Graphify are deterministic local workflows

The existing dashboard now owns one canonical Graphify workflow rooted at
`/home/liam/graphify-brain`: strict public GitHub URL intake, promptless
argv-only shallow clone, lstat quarantine scan, code-only Graphify extraction,
self-contained graph/tree previews, provenance/receipts, and repository-bound
atomic Fetch, Re-fetch, and Rebuild publication. Graph artifacts are served only
through provenance-bound allowlisted routes with regular-file and containment
checks; preview iframes use `sandbox="allow-scripts"` plus a no-network CSP.
Query, explain, affected, and path remain deterministic. Model-assisted work is
available only as a clearly marked queue-item creation action and never starts a
model from Graphify. The dashboard shell also uses local system fonts so this
surface has no runtime CDN dependency.

## 2026-07-13 — Desktop dashboard launch is authoritative

The Windows desktop adapter now calls the Linux runtime's serialized
`desktop-start` path. Each desktop launch first terminates only canonical-root
orchestration-runner, dashboard uvicorn `:8010`, and Vite/esbuild `:3010`
processes, logging every PID it kills, then starts one backend and one
frontend. It preserves the desktop launcher's dashboard-only contract and
does not restart the orchestration runner. Process matching excludes Hermes,
North Shore, wrong-port, and outside-root processes.

## 2026-07-16 — Prospecting engine uses canonical Brain knowledge and local work state

The Revenue-owned `prospecting_daily_run` and `prospecting_week_review`
workflows are registered as pre-seeded v0 skills. ICP variants, query bank,
rotation plan, and qualitative prospect pages live only in the canonical
Business Brain; the append-only quantitative ledger remains local at
`queue/prospects.jsonl`. Every discovery/drafting run is no-send and every
third-party LinkedIn/CRM action remains manually approval-gated.

## 2026-07-13 — Queue workers get a configurable exploration-safe timeout

Dashboard-assigned workers now default to a 1,200-second timeout, accept the
`AOS_QUEUE_WORKER_TIMEOUT_SECONDS` environment override, and enforce a
900-second floor. Superseded by the independently configurable agent/lease
contract recorded on 2026-07-17; the old variable remains a compatibility
fallback only.

## 2026-07-13 — Verbose Cockpit commands preserve instruction context

Cockpit commands longer than 120 characters or containing newlines now receive
a concise title derived from their first non-empty line while the complete
operator input remains in the queue item's context. Matched routes retain their
workflow prefix; short single-line commands retain their existing title
behavior. Command routing, ownership, and queue schema are unchanged.

## 2026-07-13 — Work Queue status counts are local toggle filters

Each Work Queue status-count tile now toggles that status in the view's
existing local filter state. The active tile shares the existing filter-chip
visual treatment, and selecting it again removes only the status filter while
preserving any other queue filters. No API, backend, or Cockpit behavior
changes.

## 2026-07-12 — Queue agent colors require persisted invocation evidence

Work Queue cards, its focus rail and selected detail, and Needs Me item borders
now use the same explicit persisted invocation-source evidence as token
attribution. Owner, lane, workbench, profile, and model metadata never supply an
agent color; items without authoritative invocation evidence render with the
neutral hairline, while human-review/input states retain the locked amber
override. Selecting a queue item also minimizes both the Work Items list and
Needs Me rail, with each remaining reachable from its compact rail.

## 2026-07-12 — Cockpit commands are deterministic local queue intake

Cockpit plain-language commands reuse command-route matching, owner inference,
and the existing queue creator. A submission creates one local `agent_todo`
item and never invokes a model or connector; unmatched commands route to the
explicitly named owner when present and otherwise to Hermes for later triage.
Selecting a Work Queue item collapses the list to a compact rail so the item
detail becomes the primary workspace, with an explicit expand control.

## 2026-07-12 — Dashboard shell uses ephemeral IDE sessions and a recoverable focus rail

Dashboard destinations now live in one grouped, collapsible sidebar while the
top bar is utility-only. Session tabs remain React view state: Cockpit is
pinned first, one preview is reused until pinned, and eight tabs is the cap.
Queue focus mode collapses non-selected tasks into an ID/color/state rail, and
Needs Me collapses to a visible amber count strip. No tab, focus, or rail state
is written to the backend, queue, filesystem, or browser durable storage.

## 2026-07-12 — Unavailable token usage is never rendered as exact zero

Dashboard token summaries treat an all-zero usage block with a non-empty
`unavailable` list as unavailable, not known zero. Ledger rows say
`unavailable`; periods containing both exact usage and missing components say
`known + gaps`; periods with no known usage say `unavailable`. This preserves
the schema's structural zeros without presenting them as reported model usage.

## 2026-07-12 — Buildout uses one final integrated human review

Definition `linux-authority-r3` removes the obsolete routine Pass 2 operator
checkpoint. Pass 2 performs its automated/build/browser/screenshot/visual proof
inside its implementation session, closes `done`, and unlocks Pass 3 through
the existing dependency runner. Normal Passes 1–9 continue sequentially; the
non-executable parent enters the one planned integrated `human_review` only
after all normal children have done evidence. Existing exceptional safety
states and the one bounded consolidated correction cycle remain unchanged.

## 2026-07-11 — Workflow aggregates and one bounded correction cycle

`owner_type=workflow` now marks a queue record as a non-executable aggregate;
all starter-agent `next` and direct claim paths reject it regardless of display
owner/status. Dependency advancement routes generic children to executable
`agent_todo` before any review gate, while the tagged historical acceptance
fixture retains its established behavior. When all package-identity children
are done with done receipts, deterministic orchestration moves the parent to
`human_review`. The existing review-close endpoint permits one consolidated
Needs changes note, creates one Codex `pass:correction-1` child, holds the
parent in non-actionable `inbox`, then returns it to review after correction;
a second request for that definition version is rejected.
Final workflow approval writes one idempotent `final-closeout` review receipt,
distinct from the earlier Needs-changes receipt even when both actions occur
within the same timestamp second.

## 2026-07-11 — Lock release is bound to exact owner identity and durable namespaces
Queue and package directory locks now capture protocol/package identity, token,
host, runtime, PID, process-start identity, and acquisition timestamp, and
release only when the complete validated owner record is unchanged. Candidate,
publication, quarantine, restoration, release, and deletion transitions fsync
their containing directory; a publication-sync failure removes the canonical
entry and retains noncanonical evidence. Empty orchestration ticks no longer
rewrite queue or persistent tick-lock metadata. The existing Hermes launcher
uses a typechecked production dist from the current install via the CLI's
supported `HERMES_WEB_DIST`/`--skip-build` contract and PID guards duplicates.

## 2026-07-11 — Linux-native storage is the sole Agentic OS authority
The canonical live root is `/home/liam/agentic-os-live`, configurable through
`AOS_ROOT` for ordinary Linux VMs and containers. Queue, package, ledger,
receipt, dashboard, runner, and orchestration mutations fail closed on native
Windows and Windows-backed mounts. POSIX durability is same-directory temp,
flush, file fsync, atomic replace, and containing-directory fsync. Windows is
only an optional WSL/browser adapter; the old `/mnt/c` repository is a frozen
rollback snapshot and native-Windows mutation proofs are superseded.

## 2026-07-08 — Dashboard v1 ACCEPTED: startup + close-hook closeout
Run 4 closed Dashboard v1 acceptance with startup hardening and live
close-hook validation.

PID misattribution note from AOS-2026-0049: uvicorn reload on Windows can
orphan a multiprocessing child serving stale code. Windows' TCP table can
attribute the `:8010` listener to a dead parent PID, making it look
unkillable. Diagnosis: find the real child via parent_pid lookup. Prevention:
the hardened launcher now does evidence-based cleanup with
`Stop-StaleAgenticOSBackend.ps1` before every start.

Startup/jsonschema root cause and fix: the launcher previously used plain
`python`, which allowed mixed interpreters and no provisioning, so backend
dependency state drifted from `dashboard/backend/.venv`. Fixed:
`Start-AgenticOS-Backend-Auto.ps1` now pins
`.venv\Scripts\python.exe`, creates the venv if missing, import-checks
`jsonschema`, installs `requirements.txt` only on failure, launches uvicorn
persistently, logs to `logs/backend-auto-stdout.log` and
`logs/backend-auto-stderr.log`, and health-checks `/api/queue/summary`.
Validated live, including across a full Windows reboot on 2026-07-08.

Queue guardrail worth knowing: `POST /api/queue/items/{id}/review-close` only
accepts items in `human_review` status; move items there first via `/status`.
This was hit during live testing.

Telegram close-hook was live-validated end to end on 2026-07-08: API
review-close on test item AOS-2026-0047 (`source: telegram`) ->
`_telegram_reply_on_close` -> bridge send -> message received on Liam's phone.
Dashboard v1 is ACCEPTED as of this date.

## 2026-07-11 — Buildout read-only gates suppress subprocess bytecode
The buildout loader's shared subprocess wrapper sets
`PYTHONDONTWRITEBYTECODE=1`. This keeps real `inspect`, `validate`, and
`status` validation paths read-only when they invoke the existing queue CLI
help contract, while leaving write-command behavior and the queue contract
unchanged. The same gate verifies locked-baseline ancestry but deliberately
does not require a clean worktree, because reconciliation repairs are reviewed
and validated while intentionally uncommitted.

## 2026-07-12 — Direct Codex usage reconciles only after process exit
The existing `tools/aos-queue.py` coordinator now owns the Direct Codex
launch boundary. `codex-run` requires an explicit work-item ID, uses the
installed CLI's supported noninteractive JSONL mode, captures combined output,
waits for exit, and replaces that completed item's existing receipt sidecar,
receipt block, and single token-ledger row from the terminal usage event.
`codex-reconcile` applies the identical in-place path to authoritative pasted
post-exit evidence. Neither path selects the newest item, appends a correction
row, invents a model identity, or creates a second runner/ledger/store.
Cached-input and reasoning-output counts remain capture-evidence metadata while
the standard input/output totals retain their existing schema meaning.

## 2026-07-12 — Codex invocation usage is independent of queue status
Codex reconciliation now keys exact persistence by work-item ID + session ID
and runs at supervised process exit for every honest queue state, including
`human_review`. Structured `turn.completed` usage outranks the same supervisor's
terminal summary; controlled operator evidence is the recovery fallback.
Unavailable may reconcile to exact, exact may not downgrade, conflicting exact
replays fail closed, and separate sessions remain separate token-ledger rows.
The existing item-level sidecar and one replaceable receipt block remain the
canonical dashboard surfaces; no second token store or queue was introduced.

## 2026-07-12 — Pass 2 rails and selection use canonical live identity
The existing Cockpit response now returns its complete derived
`human_review`/`needs_input`/`blocked` set instead of truncating the payload to
eight. The rail refreshes from the existing lightweight canonical queue-summary
endpoint, so unrelated Cockpit token/backup aggregation cannot hide operator
gates; a failed refresh retains the last good rail state. Queue selection records selection revisions
and request sequence so an older refresh cannot reapply its preferred item
after a newer click. No queue state, endpoint family, store, or lifecycle
semantics were added.

## 2026-07-12 — Dashboard Passes 3–9 remain projections over existing evidence
Lane cards, activity, schedule, artifact, pipeline, launcher, approval, and
handoff surfaces are projections over the existing queue, receipts, artifacts,
run/token ledgers, workflow contracts, and local status endpoints. No second
store, scheduler, queue, workflow builder, or approval layer was introduced.
Unknown cadence/token/status fields remain unavailable; Graphify Brain data is
not probed; and third-party output is explicitly manual/dry-run. The last child
uses generic orchestration to place the existing non-executable workflow parent
in `human_review`, preserving the one-note bounded correction contract.

## 2026-07-12 — Final Pass 2 selection, token provenance, and safe workflow editing
Queue selection now persists its canonical ID through the existing session-tab
parameters and validated browser session snapshot, preserving the prior
request-sequencing race guard. Token display sorts normalized authoritative
event timestamps newest-first and labels an invocation source only from explicit
persisted invocation evidence; owner, lane, profile, classification, and model
do not imply source. Workflow Bench uses one backend naming fallback and an
ID-only, stale-checked, atomic editor limited to canonical workflow definitions
plus the dedicated dashboard test-fixture root. Saving never executes. These
are Item 1's original Pass 2 defect repair and Liam-authorized Items 2–3 only;
no Pass 3–9 surface was added.

## 2026-07-08 — Token metering hardening (fix pass on commit 315a3a9)
Codex audit of the token-metering back end (commit 315a3a9) found four
issues; resolved as follows in `tools/aos-queue.py` and
`scripts/token_rollup.py`:

1. **Done-transition strictness.** Chose option (a): all three paths that can
   reach `done` (`status`, `receipt --status done`, `done`) now hard-refuse
   identically. `finalize_done()` builds the `token_usage` block and
   schema-validates both ledger lines *before* the item's status/receipt is
   persisted; on failure it raises and nothing is written or saved. Previously
   `status`/`receipt` soft-failed (status saved, error only on stderr) while
   `done` raised — but even `done` saved status=done before calling
   `finalize_done()`, so a "done" item could end up with no ledger entry.
   Chose strict refusal over documenting the soft-fail because the entire
   point of TOKEN_POLICY.md is visibility on every completed item; silent
   gaps defeat that.
2. **Schema validation enforced.** A run/token ledger line that fails
   `queue/run_ledger_schema.json` / `queue/token_ledger_schema.json`
   validation now raises (hard block) instead of being appended with a
   collected warning.
3. **est_cost_usd always deterministic.** Removed the caller-supplied cost
   override (`token_usage_json.est_cost_usd`, `usage_file.estimated_cost_usd`).
   Also started pricing the orchestrator component (previously excluded from
   cost entirely) at the run's confirmed model — matching the attribution
   `scripts/token_rollup.py`'s `by_model` breakdown already used — so the
   ledger's stored `est_cost_usd` and the rollup's recomputed total agree.
4. **Rollup dimensions + reconciliation.** `scripts/token_rollup.py` now rolls
   up by lane, profile, workbench, model, and budget class (was missing
   profile and workbench). It also no longer trusts a ledger line's stored
   `est_cost_usd` for any aggregate (totals, by_lane, by_budget, top_items) —
   every figure is recomputed from that line's own components on every run.
   This self-corrects historical data: regenerating `week-2026-W28.json`
   fixed the `total est_cost_usd 0.0` vs `by_model.claude-sonnet-5 0.1491`
   inconsistency to `0.1491` across every dimension, without editing the
   ledger itself.

Files touched: `tools/aos-queue.py`, `scripts/token_rollup.py`,
`queue/rollups/week-2026-W28.json` (regenerated), `context/TOKEN_POLICY.md`,
`hooks/token_budget_check.md`.

Tests: `tests.test_aos_queue`, `tests.test_aos_paths`,
`dashboard.backend.test_composio_hermes` — 69/69 pass. Manually verified in a
sandbox that a schema-invalid done-transition on all three paths (`status`,
`receipt`, `done`) leaves the item's status/receipts unchanged and appends
nothing to either ledger.

## 2026-07-07 — Created delivery_ops_documents skill
Created `skills/delivery_ops_documents` — closes AOS-2026-0042 gap, approved by
Liam directly, overrides default 3-repeat rule.

Files touched: `skills/delivery_ops_documents/SKILL.md`,
`workflows/delivery_ops_documents/workflow.md`, `decisions/DECISIONS.md`.
