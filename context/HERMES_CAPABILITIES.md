# HERMES_CAPABILITIES.md — Hermes v0.18 capability audit
> Revisit: when Hermes is upgraded, profile topology changes, or token accounting requirements change. · Last touched: 2026-07-07.

## Upgrade / Version
- Command verified from repo root: `hermes --version`.
- Installed version: `Hermes Agent v0.18.0 (2026.7.1) · upstream 05cbddc0`.
- Runtime path: `/home/liam/.local/bin/hermes`, wrapper to `/home/liam/.hermes/hermes-agent/venv/bin/hermes`.
- Version command reported: `Up to date`.
- `pipx list` could not be used as an upgrade-verification source because this sandboxed WSL home could not create `/home/liam/.local/state/pipx/log` (`Read-only file system`). No old-vault path was touched for the upgrade check.

## Profile List
Verified with `hermes profile list`:

```text
Profile           Model    Gateway    Alias    Distribution
◆default          gpt-5.5  stopped    —        —
aos-delivery      —        stopped    —        —
aos-marketing     —        stopped    —        —
aos-ops           —        stopped    —        —
aos-orchestrator  —        stopped    —        —
aos-revenue       —        stopped    —        —
```

## Kanban
- Available: yes.
- Verified surface: `hermes kanban --help`.
- Storage/model: durable SQLite-backed task board shared across profiles.
- Key commands exposed: `init`, `boards`, `create`, `swarm`, `list`, `show`, `assign`, `claim`, `complete`, `block`, `dispatch`, `watch`, `stats`, `runs`, `heartbeat`, `context`, `specify`, `decompose`, `gc`.
- Collaboration support: Kanban Swarm v1 graph (`parallel workers -> verifier -> synthesizer`) is exposed by `hermes kanban swarm`.

## Goal Contract
- Available: yes.
- Verified surface: Hermes docs and CLI command handlers for `/goal`.
- Commands documented: `/goal <text>`, `/goal draft <text>`, `/goal show`, `/goal status`, `/goal pause`, `/goal resume`, `/goal clear`, `/goal wait <pid> [reason]`, `/goal unwait`.
- Completion contract fields: `outcome`, `verification`, `constraints`, `boundaries`, `stop_when`.
- Contract behavior: when present, the continuation prompt targets the verification surface and constraints, and the judge decides `done` only when concrete verification evidence is present.
- Persistence: contracts persist in `SessionDB.state_meta` and survive `/resume`; `/subgoal` criteria compose with the contract.

## Background Subagents
- Available: yes.
- Verified surface: `delegate_task` documentation in Hermes `AGENTS.md`.
- Synchronous mode: parent waits for the child summary.
- Background mode: `delegate_task(background=true)` returns a delegation id immediately; result re-enters through the async-delegation completion queue.
- Batch mode: `tasks: [...]` runs parallel subagents, capped by `delegation.max_concurrent_children` (default 3).
- Roles: `leaf` cannot call `delegate_task`, `clarify`, `memory`, `send_message`, or `execute_code`; `orchestrator` can spawn workers when enabled and depth permits.
- Durability limit: background `delegate_task` is process-local; for restart-surviving work, Hermes points users to Kanban.

## Promptware / Prompt-Injection Defenses
- Security posture: Hermes states the OS is the only true adversarial-LLM security boundary; in-process scanners and approvals are heuristics, not containment.
- Environment filtering: Hermes strips credentials from lower-trust subprocesses by default unless explicitly allowed by operator/skill configuration.
- Approval gate: detects common destructive shell patterns and asks before execution, but is explicitly not treated as a complete adversarial boundary.
- Skills Guard: scans installable skill content for injection patterns as a review aid; operator review remains the trust boundary.
- MCP description scanner: warning-level regex patterns detect prompt override attempts, role-tag injection, concealment instructions, network commands, base64 decode references, code execution references, and dangerous imports; warnings do not block by default.
- Untrusted tool result wrapping is present in tests/implementation for high-risk tool outputs, but was not live-run in this audit.

## Auto-Resume Behavior
- CLI session resume: `--resume SESSION` resumes by ID or title; `--continue [SESSION_NAME]` resumes by name or the most recent session.
- TUI auto-resume: config default includes `display.tui_auto_resume_recent: false`; tips document `HERMES_TUI_RESUME=1` for auto-reattach behavior.
- Gateway startup auto-resume: restart-interrupted sessions are eligible for startup auto-resume, with a restart-loop guard that can skip auto-resume for a boot when restart thresholds are exceeded.
- Goal wait auto-resume: `/goal` can park on background processes or time waits and automatically resume when the barrier clears.

## Token / Usage Metadata
Verified source: `hermes --help`, `hermes_cli/oneshot.py`, and `run_agent.py`.

### One-shot `--usage-file`
Surface: `hermes -z/--oneshot PROMPT --usage-file PATH`.

Behavior:
- Writes JSON after the run.
- Best effort; write errors are swallowed.
- Written even when a run fails, with `failed: true` and optional `failure`.
- No effect outside one-shot mode.

Fields and units:
- `estimated_cost_usd`: USD estimate, numeric or null.
- `cost_status`: cost status string or null.
- `cost_source`: source of cost estimate string or null.
- `input_tokens`: token count, integer or null.
- `output_tokens`: token count, integer or null.
- `cache_read_tokens`: token count, integer or null.
- `cache_write_tokens`: token count, integer or null.
- `reasoning_tokens`: token count, integer or null.
- `total_tokens`: token count, integer or null.
- `api_calls`: call count, integer or null.
- `model`: model id string or null.
- `provider`: provider string or null.
- `session_id`: Hermes session id string or null.
- `completed`: boolean or null.
- `failed`: boolean.
- `failure`: failure string, present only when a failure argument is supplied.

### Runtime Session Counters
Surface: `AIAgent` session attributes in `run_agent.py`; some summaries print API calls and message count.

Counters:
- `session_total_tokens`: token count.
- `session_input_tokens`: token count.
- `session_output_tokens`: token count.
- `session_prompt_tokens`: token count.
- `session_completion_tokens`: token count.
- `session_cache_read_tokens`: token count.
- `session_cache_write_tokens`: token count.
- `session_reasoning_tokens`: token count.
- `session_api_calls`: API call count.
- `session_estimated_cost_usd`: USD estimate.

## Audit Limits
- No live model run was executed for this audit; verification used installed CLI help, local source, and local docs.
- No old runtime state was imported.
- The only upgrade blocker observed was the sandboxed read-only home path for `pipx list`; installed Hermes itself reported a compliant current version.
