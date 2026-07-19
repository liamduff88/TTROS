# DECISIONS.md — log of decisions that change system behavior
> One entry per behavior-affecting change. Newest first.

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
