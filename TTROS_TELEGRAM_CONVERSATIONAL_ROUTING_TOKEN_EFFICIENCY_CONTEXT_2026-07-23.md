# TTROS / Agentic OS — Telegram Conversational Routing and Token-Efficiency Repair Context

**Owner:** Liam Duff / Time to Revenue  
**Prepared:** 2026-07-23  
**Purpose:** Give Claude.ai or the Fable VS Code agent enough current context to inspect, repair, validate, and close the Telegram conversational-routing and token-efficiency defect without reopening completed Agentic OS work.

---

## 1. Prime objective

Olmec must be a practical conversational interface to Agentic OS.

Liam must be able to speak naturally in Telegram and receive a direct answer without creating a queue item, launching the full orchestration stack, or producing a work receipt unless he has actually asked the system to perform work.

The governing rule is:

```text
Question, discussion, clarification, correction, approval, status request,
receipt request, or conversational follow-up
→ answer directly in Telegram
→ no queue item
→ no workbench subprocess
→ no artifact/receipt workflow

Explicit request to execute work
→ create exactly one queue item
→ route to the requested worker/workflow
→ preserve existing idempotency, receipt, and review behavior
```

The current dangerous fallback appears to be:

```text
unrecognised normal-language message → create a task
```

The required fallback is:

```text
unrecognised normal-language message → conversational response or one concise clarification
create a task only when execution intent is explicit
```

---

## 2. Current architecture

```text
Telegram
→ existing Olmec Linux bridge
→ Agentic OS backend
→ either:
   A. direct conversational/operator response, or
   B. existing queue/runner/workbench path for explicit execution
```

Canonical runtime:

```text
WSL distro: AgenticOSClean
Linux user: liam
Repository: /home/liam/agentic-os-live
Telegram bridge: /home/liam/agentic-os-live/connectors/telegram_bridge/telegram_bridge.py
Backend: /home/liam/agentic-os-live/dashboard/backend/main.py
```

Telegram does not route through Composio. Composio is used only when an explicit task requires Gmail, Calendar, LinkedIn, or another connected service.

Do not create a second bot, bridge, queue, runner, scheduler, dashboard, approval layer, connector framework, memory system, receipt store, or orchestration layer.

---

## 3. Completed work that must remain closed

Do not reopen or redesign these areas unless the routing repair exposes a direct blocking defect:

```text
WP0–WP12
Dashboard Passes 0–10
Business Brain reconciliation
Graphify reconciliation
Phase 6B read-only Gmail capture
repository stabilization
Telegram concurrency/reliability repair
canonical Linux bridge migration
Telegram delivery idempotency
Codex fresh-process/fresh-session enforcement
Codex route repair
Gmail draft-only capability
```

Fresh-session behavior is now empirically proven through live Telegram-origin runs:

```text
AOS-2026-0177 session 019f8e6d-a599-7072-8d44-eaffe2f9f4f5
AOS-2026-0178 session 019f8e6d-b7a9-7612-bb66-a49d556a6c1c
```

Each produced one distinct queue item, one Codex execution, exactly one `thread.started`, and a different session ID. Session reuse is not the current defect.

---

## 4. Current defect

Liam expected and previously requested plain-language conversation with Olmec. Only genuine work requests should become tasks.

Some direct/operator paths are implemented and proven, especially `/status`. However, general conversational routing remains incomplete. Unrecognised natural-language messages can fall through into queue creation.

Observed failure:

Liam sent a conversational correction equivalent to:

```text
That was good, but the email needs my signature and a different closing sentence.
```

Instead of treating this as a small conversational follow-up or a bounded edit request requiring confirmation, the system created:

```text
AOS-2026-0180
worker: Hermes
profile: aos-orchestrator
```

The run then used:

```text
input: 164,561
output: 10,236
cache read: 1,896,448
reasoning: 1,233
API calls: 34
total processed tokens reported: 2,071,245
elapsed: 321.441 seconds
```

This was grossly disproportionate to a one-file signature/footer edit.

The result may have been technically correct, but the routing and execution strategy were not acceptable.

---

## 5. Token-efficiency contract

### 5.1 Direct deterministic operator questions

Examples:

```text
What is the system status?
What tasks are blocked?
What is waiting for my review?
What happened to AOS-2026-0180?
Show me the latest receipt.
Did the Gmail draft get created?
```

Required behavior:

```text
local read-only handler
zero model/agent tokens
zero queue items
zero workbench subprocesses
zero artifacts
one concise Telegram response
```

### 5.2 General conversational questions

Examples:

```text
Why did that use so many tokens?
What does this receipt mean?
Should this be a task?
Can we change the wording before running it?
What would be the best next step?
```

Required behavior:

```text
one bounded conversational model call only when deterministic logic cannot answer
no queue item
no orchestration profile
no Codex/Claude subprocess
no receipt or queue artifact
no retained conversation from an unrelated request
small, explicitly bounded context
one concise Telegram answer
```

Efficiency target:

```text
Prefer zero-token deterministic answers.
For model-backed conversation, use one call and the smallest relevant context.
Do not load full repository history, whole queue history, broad Brain context,
large retained transcripts, or orchestration prompts.
```

Liam recalls the old simple-question path using roughly 148 tokens. Treat that as a user-reported historical benchmark, not a verified current ledger value. The implementation target is not necessarily exactly 148 tokens; the target is the same order of magnitude for simple model-backed questions and zero tokens where deterministic handling is possible.

### 5.3 Explicit work requests

Examples:

```text
/work codex Fix the footer in outreach_handoff.py
Create a task to add my email signature.
Run the prospecting Gmail-draft workflow.
Use Codex to repair the failing test.
```

Required behavior:

```text
create exactly one queue item
acknowledge it clearly
route once
fresh worker process/session
one final notification
one receipt/artifact where the workflow requires it
no duplicate execution on delivery replay
```

Small tasks must use the smallest capable route. Do not send a one-file edit through full Hermes orchestration unless orchestration is genuinely required.

---

## 6. Routing classification contract

The implementation must classify Telegram input before queue creation.

### Class A — direct deterministic operator read

Must not queue:

```text
/status and natural-language status equivalents
queue counts and lists
blocked / needs-input / human-review questions
latest receipt or task-status lookup
known work-item lookup by AOS ID
health/readiness questions
simple token-ledger lookup
```

### Class B — conversational question or discussion

Must not queue:

```text
questions beginning with what, why, how, when, where, who, can, should, is, are, did, does
requests for explanation, comparison, advice, interpretation, or summary
comments and reactions
brainstorming
planning before execution
```

Use a bounded conversational response. Ask one concise clarification only when necessary.

### Class C — follow-up bound to existing context

Must not create a new task automatically:

```text
approval or rejection of a pending review
clarification requested by an existing item
correction to a just-produced draft/result
question about the latest item
request to show or explain the latest result
```

The router must bind the message to the relevant pending/recent item using explicit operator-chat context. It must not infer approval from arbitrary inbound content. If binding is ambiguous, ask which item Liam means; do not create a new task.

### Class D — explicit execution request

May create a task:

```text
explicit /work command
explicit “create a task” language
clear imperative requesting a file/code/workflow/external-system action
explicit worker selection such as Codex, Claude, or Hermes
```

Ambiguous messages default to conversation, not execution.

---

## 7. Required operator controls

Preserve the existing explicit commands:

```text
/work codex <task>
/work claude <task>
/work hermes <task>
/status
```

Add or preserve a clear explicit escape hatch for converting conversation into work, for example:

```text
Run that as a task.
Create a task for that.
/work codex ...
```

A direct conversational response may offer a compact action suggestion, but it must not silently queue it.

Do not add repeated confirmation prompts for clear explicit `/work` commands.

---

## 8. Likely code areas to inspect

Inspect live reality before editing. Likely relevant areas include:

```text
connectors/telegram_bridge/telegram_bridge.py
  message classification
  update/delivery claim
  explicit command routing
  recent/pending item binding
  queue-post fallback

dashboard/backend/main.py
  Telegram/Hermes endpoint
  natural-language route classifier
  direct operator reads
  queue creation fallback
  local conversational response path

tools/aos-orchestration-runner.py
  verify it is reached only after explicit execution classification

tools/aos_codex_policy.py
  preserve fresh-session behavior; do not redesign
```

Inspect existing tests before adding new ones:

```text
tests/test_telegram_bridge_formatting.py
dashboard/backend/test_composio_hermes.py
tests/test_aos_orchestration.py
tests/test_aos_queue.py
```

Do not inspect protected route files unless the live call path proves they are directly responsible and Liam has explicitly scoped them.

---

## 9. Implementation constraints

- Use the existing bridge, backend, queue, and workbench routes.
- Add the smallest routing layer needed before queue creation.
- Prefer deterministic intent rules for high-confidence operator reads and explicit work commands.
- Use at most one small classifier/model call for ambiguous conversational input.
- Do not invoke Hermes `aos-orchestrator` merely to answer a question.
- Do not create a queue item to ask a clarification.
- Do not create a receipt or artifact for ordinary conversation.
- Do not retain a large transcript across unrelated Telegram messages.
- Preserve Telegram delivery idempotency.
- Preserve fresh Codex sessions for explicit Codex tasks.
- Preserve Gmail draft-only restrictions; no sending.
- Preserve the canonical Linux bridge and PowerShell launcher.
- No commit or push unless Liam explicitly authorizes it.

---

## 10. Focused acceptance tests

Do not run a broad suite during repair. Run the smallest affected tests, then one final affected regression set.

### 10.1 No-task conversation tests

Each message must produce one direct reply and zero queue growth:

```text
Why did the last run use so many tokens?
What is waiting for my review?
What happened to AOS-2026-0180?
Can you explain the last receipt?
That answer was good, but I want to discuss the closing sentence first.
```

Verify:

```text
queue item count unchanged
no runner process
no Codex/Claude subprocess
no orchestration artifact
no work receipt
one Telegram response
```

### 10.2 Existing-item binding tests

```text
I approve that.
No, revise the closing sentence.
Why is that blocked?
Show me the receipt.
```

Verify:

```text
message binds to the correct pending/recent item when unambiguous
no new task is created
ambiguous binding asks one concise question
```

### 10.3 Explicit work tests

```text
/work codex Return exactly ROUTE_PROOF_PASS and do nothing else.
Create a task to update the prospecting email signature.
```

Verify:

```text
exactly one queue item per request
exactly one process/session
one acknowledgement
one final notification
no duplicate on delivery replay
```

### 10.4 Token-efficiency proof

Collect exact evidence for representative routes:

```text
deterministic status question: no agent invocation
queue/receipt lookup: no agent invocation
simple conversational question: one bounded call, no queue
explicit tiny work request: smallest capable worker route, no full Hermes orchestration unless required
```

Report exact available token values. Never estimate.

### 10.5 Live Telegram proof

After focused tests pass, run a bounded real proof from Liam’s Telegram chat:

1. Ask one natural-language status/question message.
2. Confirm direct answer and zero queue growth.
3. Ask one conversational follow-up.
4. Confirm direct answer and zero queue growth.
5. Send one explicit `/work codex` proof.
6. Confirm exactly one new queue item and one fresh Codex session.

Do not send email or mutate any external service during this proof.

---

## 11. Definition of done

The repair is complete only when all of the following are true:

```text
Liam can talk naturally to Olmec.
Questions and discussion do not create tasks.
Status, queue, receipt, and task lookups are deterministic and token-free.
Ambiguous conversation defaults to conversation or clarification, not execution.
Approvals/corrections bind to the intended item or ask which item.
Only explicit work requests create queue items.
Tiny work uses the smallest capable route.
No ordinary question launches Hermes orchestration.
Real Telegram proof shows zero queue growth for conversation.
Explicit /work behavior and delivery idempotency remain green.
Exact token evidence demonstrates a large efficiency improvement.
No broad architecture was reopened.
No commit or push occurred without Liam’s approval.
```

---

## 12. Required closeout

Return:

```text
PASS / NEEDS ATTENTION
Files touched
Root cause
Routing behavior before and after
Focused tests run and exact results
Live Telegram proof
Queue growth proof
Token evidence by route
Protected areas
Blockers
Next action
Token usage
```

Do not claim PASS from mocked tests alone. A live Telegram conversational proof is required.

---

## 13. Local-workbench execution prompt

Use the following as the implementation instruction after this context has been read:

```text
PERMISSION MODE — SCOPED LOCAL TASK APPROVED
Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.
Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.
Stop only for real external/destructive actions.

Read TTROS_TELEGRAM_CONVERSATIONAL_ROUTING_TOKEN_EFFICIENCY_CONTEXT_2026-07-23.md and repair the complete Telegram conversational-routing and token-efficiency defect.

Work in /home/liam/agentic-os-live. Inspect the current live call path before editing. Preserve completed Telegram concurrency, delivery idempotency, fresh Codex sessions, Gmail draft-only boundaries, and the canonical Linux bridge.

Required outcome: ordinary questions, discussion, clarifications, approvals, corrections, status requests, queue/receipt lookups, and ambiguous messages must not create queue items. Only explicit execution intent may create a task. Deterministic operator reads must use zero agent tokens. General conversation may use at most one tightly bounded model call and must not invoke the queue, runner, Codex/Claude subprocesses, or Hermes aos-orchestrator. Explicit small work must use the smallest capable route.

Run narrow tests during repair, then one affected regression set and the bounded live Telegram proof defined in the context file. Diagnose and repair failures in the same task. Do not run the broad repository suite. Do not commit or push.
```

