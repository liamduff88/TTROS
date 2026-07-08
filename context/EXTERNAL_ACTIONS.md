# EXTERNAL_ACTIONS.md — what's free, what's gated
> Revisit: on a new connector, a boundary incident, or a compliance change. · Last touched: 2026-07-07.

## The line
Native access first, mutation guard second, no permission theatre. Free
because they touch nothing outside this system's own read path:

```
read / search / list / fetch / status / get / info
draft / prepare / summarize / recommend (local artifacts only)
create/update local work items, receipts, packets, results, scoped files
```

Gated — requires an explicit command naming the specific action, every time:

```
send (email, message, DM, outreach)
write / publish / post (LinkedIn, website, any public surface)
push (GitHub)
mutate (CRM/GHL, Calendar booking, Drive/Docs/Sheets writes beyond a draft)
delete / archive / move broad data
connect a new account or grant a new scope
spend money
touch a production or client-owned system
```

"Explicit command" means Liam names the action and the target in that turn —
a general go-ahead on the task ("build the proposal") is not authorization to
send it. Approval is per-action, not per-project.

## Connector spine
Composio is the shared access path (Gmail, Calendar, Drive, Docs, Sheets,
GitHub, LinkedIn, YouTube, Instagram, Maps, Agent Mail, Reddit — CRM/GHL
later). Connectors are access paths, not agents; the free/gated split above
applies identically regardless of which connector carries the call.

## CASL / outreach-specific gate
No lead is contacted without a passing email-safe/CASL check and a stated
outreach basis on the draft (rules/never.md #10). Failing that check removes
the lead from outreach entirely, not just downgrades it — never.md #12
applies (report, don't quietly drop and forget).

## Verification, not assumption
Sandbox/CLI network checks never stand in for live connector status. Live
checks route through PowerShell → WSL CLI. If a live check can't run, the
receipt says so — it does not report success from an unverified assumption.

## Enforcement
Hooks: pre_external_action.md (the guard that fires on any gated verb before
execution) and secret_exposure_check.md (credentials never printed, even to
confirm an action is safe). Mirrored in rules/never.md #1, #6, #10, #11.
