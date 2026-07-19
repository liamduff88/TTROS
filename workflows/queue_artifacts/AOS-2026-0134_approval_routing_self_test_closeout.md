PASS

Work item:
- AOS-2026-0134

Files touched:
- /tmp/aos-approval-routing-self-test-AOS-2026-0134.marker
- queue/receipts/AOS-2026-0137-approved-marker.md
- workflows/queue_artifacts/AOS-2026-0134_approval_routing_self_test_closeout.md
- queue/work_items.jsonl

Validation:
- Existing approval-gated child item AOS-2026-0137 is done with receipt queue/receipts/AOS-2026-0137-approved-marker.md.
- Confirmed marker exists at /tmp/aos-approval-routing-self-test-AOS-2026-0134.marker after operator approval.
- No Gmail action, external action, Git action, protected-path access, secrets exposure, or destructive action outside scope was performed.

Artifacts:
- workflows/queue_artifacts/AOS-2026-0134_approval_routing_self_test_closeout.md
- queue/receipts/AOS-2026-0137-approved-marker.md
- /tmp/aos-approval-routing-self-test-AOS-2026-0134.marker

Blockers:
- None.

Next action:
- None.

Token usage:
- unavailable from current CLI output


<!-- token_usage:AOS-2026-0134 -->
## token_usage
```json
{
  "token_usage": {
    "orchestrator": {
      "input": 0,
      "output": 0
    },
    "subagents": [],
    "workbenches": [],
    "totals": {
      "input": 0,
      "output": 0
    },
    "est_cost_usd": 0.0,
    "unavailable": [
      "orchestrator tokens",
      "subagent tokens",
      "workbench session totals"
    ]
  },
  "profile_invocation": {
    "requested_profile": "aos-orchestrator",
    "fallback_profile": "default",
    "invoked": false,
    "native_invocation": "unavailable",
    "resolved_profile": "aos-orchestrator",
    "evidence": "`hermes profile show aos-orchestrator` rc=0; profile present WITH configured model",
    "reason": "Profile 'aos-orchestrator' has a configured model, but `hermes profile use` is prohibited for queue routing (queue/profiles/README.md); the queue does not switch the sticky default. Native switching intentionally not performed."
  }
}
```
