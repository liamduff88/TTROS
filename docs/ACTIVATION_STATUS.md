# TTROS Agentic OS — Activation Status
> Revisit after any operating-profile, connector, protection-boundary, queue, Business Brain, search, Graphify, prospecting, dashboard, startup, or backup change. · Last touched: 2026-07-31.

**Overall: PASS — core intended capabilities are OPERATIONAL.**

This matrix uses the operational ladder literally: PLANNED → BUILT → WIRED →
AUTHENTICATED → INVOKABLE → END-TO-END PROVEN → OPERATIONAL. Only the final
state counts as complete. Fresh live behavior on 2026-07-31 supersedes older
PASS labels. Detailed evidence is in
`proofs/final-operational-verification-2026-07-31/OPERATIONAL_VERIFICATION_CLOSEOUT.md`.

The requested `TTROS_WORKING_SYSTEM_CSUITE_OPERATING_RULES_2026-07-31.md` was
not present. Current authority came from `AGENTS.md`, `CODEX.md`,
`context/PATHS.md`, `context/OPERATING_BASELINE.md`,
`context/OPERATOR_CONTRACT.md`, `context/LOOP_POLICY.md`,
`context/MEMORY_ROOT.md`, `context/MEMORY_PROMOTION_POLICY.md`, the current
rules, decisions, profile cards, workflow catalog, and live implementation.

## Operational capability matrix

| Capability | Business purpose | Normal invocation path | State | Latest proof | Blocker / optional authority |
| --- | --- | --- | --- | --- | --- |
| Operator conversation | Let Liam think and ask without creating work | Telegram/Cockpit → `/api/wsl-hermes` → `aos-orchestrator` operator-lean | OPERATIONAL | Fresh ordinary conversation used the live model, created zero queue items, and recorded exact usage | None |
| Deterministic operator reads | Answer status, queue, and receipt questions without model cost | Operator classifier → local queue/search/status readers | OPERATIONAL | Fresh queue-status request returned canonical state with zero queue delta and `Token usage: no agent invocation` | None |
| Execution intent | Turn explicit work requests into exactly one governed item | Operator classifier → canonical queue → runner | OPERATIONAL | One request created one Operations item; normal runner claimed it, used `aos-ops`, wrote artifact/receipt, and stopped at human review | None |
| Hermes orchestrator | Give executive guidance and coordinate lanes | `aos-orchestrator` profile → scoped Brain → named department profiles | OPERATIONAL | Post-repair integrated acceptance delegated useful work to all four profiles with no default fallback | None |
| Revenue executive | Rank commercial work and preserve outreach gates | Revenue queue owner → `aos-revenue` | OPERATIONAL | Fresh routed Revenue item and two integrated invocations used `aos-revenue`, produced useful opportunity review, and stopped for Liam | None |
| Marketing executive | Prepare positioning-aligned assets without publishing | Marketing queue owner → `aos-marketing` | OPERATIONAL | Fresh five-post campaign plus integrated draft used current positioning/voice and reached human review; nothing published | None |
| Delivery executive | Turn safe scoped context into implementation-ready delivery work | Delivery queue owner → `aos-delivery` | OPERATIONAL | Fresh fictional-client first-week plan used only the named fixture and global delivery note; no live client workspace was opened | None |
| Operations executive | Coordinate priorities, review gates, follow-up, and lane handoffs | Operations queue owner → `aos-ops` | OPERATIONAL | Fresh priority brief and integrated coordination output ordered cross-department work and reached human review | None |
| Prospecting | Produce evidenced, scored, reviewable opportunities | Request → Revenue → `prospector.py` → daily engine → ledgers/packages | OPERATIONAL | Bounded replay read 9 scoped Brain notes, validated 2 signals and 2 duplicates/prior-contact states, produced 2 packages, one Gmail draft reference, one manual LinkedIn package, and zero sends | None |
| Prospecting daily/weekly contracts | Keep the operating cadence reachable | Skill/workflow catalog → `prospecting_daily_run` / `prospecting_week_review` | OPERATIONAL | Root entry point and daily engine ran idempotently; workflow/skill regression pack passed; both remain catalogued | None |
| Canonical Business Brain | Supply current governed company/client context | Logical pointer or scoped query → registry-approved vault | OPERATIONAL | Fresh pointer, search, and Graphify reads returned content hashes and actual-read provenance; invalid scope failed closed | None |
| Brain promotion | Promote durable knowledge under the right authority tier | Candidate evaluation → deterministic write or review-tier queue | OPERATIONAL | Fresh promotion/full-loop tests prove safe deterministic writes, review-tier routing, never-promote enforcement, rollback, and later retrieval | None |
| Memory Board | Let Liam safely edit canonical global Brain notes | Dashboard → memory API → optimistic canonical save | OPERATIONAL | Current browser proof saved, reopened, restored, and reopened two canonical notes with no backup exposure or console/HTTP errors | None |
| Graphify | Improve discovery without becoming authority | Scoped Brain query → read-only derived graph → canonical note open | OPERATIONAL | Fresh unchanged build: 29 sources/29 notes; broad query returned 8 scoped actual reads from a fresh graph; graph bodies remain outside projection | None |
| Search/indexing | Find current Brain, OS, result, and receipt metadata safely | `/api/search` / indexer scan | OPERATIONAL | Fresh scan published 1,259 inputs with zero failures; live index reports 1,336 files after capture publication; scope filter rejects unknown scopes and path-only results expose no bodies | None |
| Queue/runner/orchestration | Reliably move governed work through dependencies and review | Queue create/claim/run/status/receipt + deterministic tick | OPERATIONAL | Real items reached human review; 112 focused queue/orchestration/guard tests cover dependencies, needs_input, correction/resume, done, idempotency, and receipts; no runnable stale fixture remains | None |
| Executable protections | Enforce receipt, isolation, external, publish, path, and secret boundaries | Native `pre_tool_call` hook plus queue done/external-action adapters | OPERATIONAL | `hooks doctor` passed on all five profiles; focused guard/queue tests passed, including actual completion and external-action boundaries | None |
| Gmail read-only capture | Ingest allowed inbound metadata without mailbox mutation | Existing Hermes cron → Linux launcher → Composio read-only actions | OPERATIONAL | Gateway and cron live; bounded scheduled poll advanced the cursor incrementally, added metadata, opened no bodies/attachments, and made zero Gmail/external mutations | None |
| Gmail draft-only | Prepare reviewable email while making send impossible | Prospecting → item-bound Gmail draft capability → human review | OPERATIONAL | Existing draft replay remained idempotent; send stays outside the allowlist; draft bodies stay off unsafe status/search surfaces | None |
| Dashboard/operator surfaces | Give Liam a usable control plane | Linux backend :8010 + Vite :3010 | OPERATIONAL | Browser traversed Cockpit, Work Queue, Message Board, Memory Board, Skills Board, and Results/Receipts; all rendered with zero console/HTTP failures | None |
| Skills/workflows | Make current playbooks callable under queue governance | Skills Board/catalog → `tools/aos-workflow.py` → queue-tracked run | OPERATIONAL | 24 skill files present; 12 catalog workflows list/show/prepare; 72 workflow/prospecting tests plus a dry-run Operations packet passed | Trust remains governed by `queue/skill_trust.jsonl`; presence is not graduation |
| Backup/recovery | Preserve the authoritative Linux OS for restoration | Existing daily Windows launcher → Linux backup script → Linux-native snapshots | OPERATIONAL | Scheduled task is enabled/ready, points to Linux authority, last result 0; final post-closeout snapshot has 2,124 readable files, exclusions verified, and dashboard reports `fresh_success` | None |
| Runtime/startup | Start and keep the normal company operating layer usable | `tools/aos-linux-runtime.sh start` + Hermes gateway | OPERATIONAL | Backend, frontend, runner, Telegram transport, and Hermes gateway are running; backend/frontend health checks pass; one canonical orphaned Vite process is safely adopted | None |
| Composio/connectors | Supply authenticated current connector capabilities | Repository adapter → live Composio CLI | OPERATIONAL | Live read-only status is current; required Gmail is active and both capture/draft actions are discoverable; current LinkedIn/manual-package support is available | Expired Apollo/Google Maps/Facebook/WhatsApp connections are unused by the current normal path |

## Intentionally optional or dormant

| Item | State | Why it is not a completion blocker | Current authority |
| --- | --- | --- | --- |
| Antigravity workbench | PLANNED | It activates only after its first real task | `AGENTS.md`; `ANTIGRAVITY.md` |
| Standing-goal recurring verifier | BUILT | It is an explicitly read-only unscheduled stub; no new recurring job is authorized | `loop/verify-goals.sh`; `context/MEMORY_PROMOTION_POLICY.md` |
| Fast-path demonstrations AOS-2026-0181/0182/0183 | BUILT | Demonstration fixtures, not dependencies of the normal runtime; left untouched | Their existing queue contracts and the activation instruction |
| Composio developer-project binding | BUILT | The live consumer CLI/adapter is the current operating spine; creating/binding a developer project is a separate external configuration action | `connectors/composio_access_adapter.py`; current connector contract |
| Cached connector snapshot | BUILT | Explicit fallback only; live CLI evidence is authoritative | `connectors/composio_access_adapter.py` |

## Final acceptance

The integrated post-repair run passed: Liam’s focus question used current
Brain context; Revenue produced reviewable opportunities; Marketing produced a
draft asset; Delivery produced fixture-scoped delivery work; Operations ordered
the work; Hermes coordinated all four; human review and receipts remained
intact; and no external action occurred.

Agentic OS is therefore usable now as Time to Revenue’s executive and business
operating layer. The next action is normal business use, not another
infrastructure audit.
