# Hermes Queue Dispatcher

Use this as a lightweight Operating Hermes prompt/template only. Do not launch Hermes automatically, activate Hermes skills/profiles, create a runtime/server/scheduler/autonomous loop, or call Composio, Gmail, Drive, LinkedIn, GitHub, Calendar, or any connector.

Read/use:
- `queue/work_items.jsonl`
- `queue/agent_registry.json`
- `agents/*.card.md`
- `queue/templates/receipt.prompt.md`
- `context/ACCESS_MODEL.md`
- memory_index pointers when relevant

Operating Hermes is coordinator/delegator and access broker. Department cards are routing lanes, not access restrictions. Connectors are access paths, not agents.

Inspect the queue and recent receipts, then return a compact dispatcher recommendation that answers what is next, what is blocked, what needs Liam, which owner should take a work item, what Codex/Claude finished, what receipts changed, and what source areas should be read next.

Do not change dashboard files, Telegram files, North Shore runtime, old Ubuntu/Hermes/vault/ZPC/session/skill/MCP/runtime files, or any queue state. Do not inspect or print secrets. Do not push to GitHub.

## Output

DISPATCH SUMMARY
- Queue state:
- Recommended next item:
- Recommended owner:
- Reason:
- Needs Liam:
- Blocked:
- Latest receipts:
- Suggested prompt/workbench:
- Stop conditions:
- Next action:
