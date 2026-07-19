# Agentic OS Access Model
> Revisit: when connector authority changes. · Last touched: 2026-07-17.

This model keeps Agentic OS native, useful, and efficient without turning access into bureaucracy.

## Prime Rule

- Native access first.
- Mutation guard second.
- No permission theatre.
- No bureaucracy.

## Path Convention

Use `AOS_ROOT` or root-relative paths for Agentic OS code, docs, and templates. New work must not add hardcoded Windows or WSL absolute workspace paths.

## Default Allowed Access

When relevant to a scoped task, Agentic OS may:

- Read/search/list/fetch/status from the Agentic OS Live workspace.
- Read/search relevant TTROS Business Brain / Obsidian files through memory pointers.
- Read/search queue, packets, results, logs, context, and memory_index.
- Read/search/get/list/fetch/status through the connector spine for Gmail, Calendar, Drive, Docs, Sheets, GitHub, LinkedIn, and other connected tools.
- Draft/prepare/summarize/recommend locally.
- Create Gmail drafts only through the exact idempotent draft adapter; no
  Gmail send, reply, forward, schedule-send, draft mutation, or label mutation.
- Create/update local work items, receipts, packets, results, and local scoped files.
- Validate changed local files.
- Inspect metadata/status without exposing secrets.

## Explicit-Stop Actions

Stop for human review or explicit instruction before:

- External sends/messages/posts.
- Publish actions.
- GitHub push.
- CRM/GHL mutation.
- Calendar/Drive writes beyond explicit status tasks. Gmail permits only exact
  draft creation; every transmission and other mutation is forbidden.
- Calendar booking.
- Deleting/archiving/moving broad data.
- Spending money.
- Production/client-system mutation.
- Exposing or printing secrets/API keys/OAuth tokens.
- Inspecting secret values unless explicitly requested for a recovery task.
- Old vault/runtime import.
- Autonomous recurring external jobs.

## Role Model

- Operating Hermes is the access broker/delegator.
- Department cards are routing lanes, not permission walls.
- Connectors are access paths, not agents.
- Work Queue records source references, allowed action intent, stop conditions, and receipts.
- Codex/Claude are scoped workbenches.
- TTROS Business Brain is durable memory.
- Old vaults are archive/quarantine only.

## Queue Behavior

- Work items should name the source areas needed, not paste entire vaults.
- Use source references wherever possible.
- Receipts capture what was accessed at a category/path level without printing sensitive values.
- If external mutation is needed, move status to human_review or needs_input.

## Token/Memory Efficiency

- Do not paste the full access doctrine into every prompt.
- Reference context/ACCESS_MODEL.md when needed.
- Use targeted reads/searches, not broad crawls.
- Summarize only relevant snippets.
- Promote stable decisions/results to TTROS Business Brain only when useful.
