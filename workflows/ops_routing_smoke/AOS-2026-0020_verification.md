# Operations Routing Smoke Verification

Work item: AOS-2026-0020
Lane: operations
Profile requested: aos-ops
Provider requested: <EXACT_PROVIDER>
Model requested: gpt-5.5

Purpose:
Verify the local Agentic OS queue path can carry explicit Operations lane routing metadata into an attempted Hermes coordinator run without using native Hermes profile switching, connectors, Telegram, North Shore, or external project systems.

Local path used:
1. Created the queue item with `tools/aos-queue.py create`.
2. Claimed the queue item with `tools/aos-queue.py claim AOS-2026-0020 operations`.
3. Prepared this local artifact under `workflows/ops_routing_smoke/`.
4. Attempted the Hermes coordinator with explicit `--provider` and `--model` flags.

Result:
The queue path and explicit coordinator invocation were reached, but Hermes rejected the supplied provider before a worker completion.

Non-secret coordinator error:
`hermes -z: agent failed: Unknown provider '<exact_provider>'. Check 'hermes model' for available providers, or run 'hermes doctor' to diagnose config issues.`

Final queue status:
blocked; see `queue/receipts/AOS-2026-0020.md`.
