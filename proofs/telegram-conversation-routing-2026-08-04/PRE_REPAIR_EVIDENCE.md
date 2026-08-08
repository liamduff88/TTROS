# Telegram conversational-routing regression — pre-repair evidence
> Point-in-time evidence · Created: 2026-08-04 · Revisit: never; preserve with the linked historical logs.

## Exact incident timeline

- Europe/Dublin `2026-08-04 18:02:47.846` / UTC `17:02:47.846`: Hermes session `20260804_180247_9c71a6` began for Telegram delivery `telegram-update-635544800` in sticky scope `5b45fd27ca66ca1e4dbc339c`.
- UTC `17:02:57.649`: the operator-lean model called `mcp__operator__escalate_to_executive` for niche/ICP priority judgment.
- UTC `17:03:48.319`: the nested executive tool returned a substantive answer after the token ledger recorded `50.543` seconds for invocation `operator-escalation-770ee97664b34af69321a71ce57f9c1c`.
- Europe/Dublin `18:04:16.312` / UTC `17:04:16.312`: the backend recorded operator invocation `hermes-4247efa218cd4b298eb8540dae28dd88` with unavailable usage. This is exactly 90 seconds after the MCP servers started at local `18:02:46`; `AOS_OPERATOR_LEAN_TIMEOUT_SECONDS` was the default `90` seconds.
- The Hermes state database contains the user turn, the escalation tool call, and the complete tool result, but no final assistant message. The backend terminated the outer operator turn while it was trying to complete after the nested result.

Sources retained in place:

- `logs/token_usage.jsonl` records 494–495.
- `/home/liam/.hermes/profiles/operator-lean/state.db`, session `20260804_180247_9c71a6`, messages 221–223.
- `/home/liam/.hermes/profiles/operator-lean/logs/mcp-stderr.log`, local timestamps `18:02:46`, `18:02:47`, and `18:02:57`.

## Exact retry message

```text
Continue from my last unanswered message.

Save this as my current priority: I need to choose a practical niche or target market for cold prospecting, develop a strong prospecting approach, and build visible specialization. I do not yet know which niche to choose.

Do not create a queue item or start execution. Briefly summarize what this means strategically, then ask me the single most useful question for narrowing the niche options.

Keep the response under 150 words.
```

- UTF-8 bytes: `474`
- SHA-256: `de119f16b7a3c11b9767c363f320e66a2cfb95a47f4e9ca3369fe2f1d8adb2e5`

## Deterministic pre-repair reproduction

The production backend function was invoked against the live queue with the exact text, source `telegram`, reply target `1320777128`, and delivery `pre-repair-exact-retry` before code repair.

```json
{
  "approval_routed": true,
  "state": "approval-target-ambiguous",
  "candidate_count": 18,
  "first_candidate": "AOS-2026-0128",
  "queue_count_before": 475,
  "queue_count_after": 475,
  "queue_sha256_before": "746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228",
  "queue_sha256_after": "746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228"
}
```

Backend output began:

```text
NEEDS ATTENTION
Approval matches multiple pending items; reply with exactly one AOS item ID.
Safe candidate IDs: AOS-2026-0128 — wsl.exe -d AgenticOSClean ...
```

The unchanged queue proves no item was created, resumed, accepted, or otherwise mutated. The Telegram completion formatter treated the ambiguity as a queue failure and extracted the first AOS-shaped string:

```text
NEEDS ATTENTION
Work item: AOS-2026-0128
Final state: needs_attention
Files touched: None reported
Validation: NEEDS ATTENTION
Connector access: No connector action reported
Token usage: unavailable from current CLI output
Blockers: See local logs
Next action: Review local logs
```

## Historical AOS-2026-0128 preimage

- Queue record line: `128`
- Created: `2026-07-17T11:11:28Z`
- Current historical state at incident: `human_review`
- Primary receipt mtime: `2026-07-17 12:14:03.273187842 +0100`
- Primary receipt SHA-256: `1b7e77501e17a38951ad34dc687f8badef97f48dc72285f7be0f71c47d1444bc`
- The item had no incident delivery ID and was only the lexically first historical candidate emitted by the approval ambiguity.

## Branch verdict

- First timeout: outer `operator-lean` execution timeout after an avoidable nested executive escalation consumed 50.543 seconds; not Context Assembler, queue work, stale session routing, worker lease, or Telegram polling.
- Retry misroute: `_telegram_approval_intent` accepted any text beginning with `Continue`; `_try_telegram_approval` then correlated historical pending Telegram items with missing chat IDs through the operator allowlist.
- Why 0128 appeared: it was the first candidate string in `_approval_clarification`; `compact_telegram_closeout` extracted and displayed it as a work item.
- AOS-2026-0128 disposition: historical lookup text only; not created, reused, bound, resumed, or changed.
