# Recurring schedule proof
> Expires: when the Phase 6B cadence, entry point, or Hermes scheduler state changes. · Last touched: 2026-07-15.

Result: **PASS**.

- Existing scheduler machinery: Hermes cron and its existing WSL-supported manual gateway mode.
- Job name: `TTROS Phase 6B Gmail capture`.
- Job ID SHA-256: `0287496246af59319ab292b1b85a0c21ebba231c0228e0116b9d2412a2a0d52b`.
- Schedule: `*/15 * * * *` (every 15 minutes).
- Mode: `no-agent`; no scheduler LLM call.
- Workdir: `/home/liam/agentic-os-live`.
- Script: `ttros-gmail-capture.sh`; wrapper SHA-256 `d242d4b6b999743059a1074712ea020cf6653091cbd9a378cb3b9e33fc1632f1`.
- Wrapper delegates only to `/usr/bin/timeout --signal=TERM 180 /usr/bin/python3 .../tools/aos_capture_live.py poll --scheduled`.
- Entry-point SHA-256 at proof freeze: `80f4af0eb33d7ed16c9492bd8589fc3d58bea419cf06a9feb56f9c67ca1dc4a6`.
- Non-overlap proof: scheduled invocation while the production lock was held returned `already_running`, provider actions zero.
- Scheduler-trigger proof: manual `hermes cron run` completed successfully through the exact job.
- Automatic proof: Hermes fired without a manual trigger at `2026-07-15T23:15:35.389834+01:00`; the receipt was `scheduled_entry=true`, successful, and mutation-free.
- Next run registered at proof freeze: `2026-07-15T23:30:00+01:00`.
- Gateway: running in Hermes' documented manual WSL mode with an active ticker heartbeat.

The three pre-existing overdue jobs pointed at the frozen legacy Agentic OS workdir. Their definitions were preserved and their state was changed from active to paused before the gateway started, preventing unrelated legacy runners from firing. Exactly one job is active: Phase 6B capture.

The first script placement was rejected by Hermes before execution because this scheduler resolves scripts in the active orchestrator profile. The unchanged wrapper was placed in that scheduler-owned scripts directory without inspecting or changing profile configuration; subsequent scheduled runs passed.

Token usage: no agent invocation.
