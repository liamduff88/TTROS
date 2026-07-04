# Business Sub-Agents

Not a framework. No harness, no queue, no runtime, no dashboard panel, no
autonomous loop. Just instruction cards for lightweight Hermes-delegated
workers.

## Architecture

Main Hermes Orchestrator
→ delegates to one sub-agent
→ sub-agent returns compact RESULT + RECEIPT
→ orchestrator approves, asks for one retry, or sends back to Liam

## Agents

- [marketing.md](marketing.md) — content, positioning, offer messaging
- [revenue.md](revenue.md) — leads, outreach, proposals, CRM
- [delivery.md](delivery.md) — client-facing docs and implementation work
- [operations.md](operations.md) — priorities, reviews, internal state

## Token policy

- One orchestrator call, one sub-agent call per task.
- Maximum one retry unless Liam explicitly asks for more.
- No autonomous loops. No background swarms.
- No agent-to-agent chatter unless the orchestrator explicitly delegates it.
- Deterministic, local, file-based work first. Model tokens are for
  judgment, drafting, synthesis, and reasoning only.
- Receipts instead of long explanations.

## Output format

Every sub-agent replies in this shape:

```
RESULT:
<compact useful answer>

RECEIPT:
- Agent:
- Task:
- Files touched:
- Evidence / validation:
- Needs Liam approval:
- External action taken:
- Next action:
```

Any workflow with its own output format (e.g. Revenue's LinkedIn Relationship
Outreach) overrides this default for that task only.

## Ground rules

- No mass messaging, no scraping, no fake personalization, no unsupported
  claims, ever.
- No external send (LinkedIn, email, CRM) without Liam approving the exact
  recipient and exact message.
- Draft-first is the default posture for anything outward-facing.
