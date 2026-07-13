# Pass 5 — read-only schedule
> Revisit: when an existing recurring-operation cadence contract changes. · Last touched: 2026-07-12.

PASS

- Mission Control now shows existing backup, System Watch, AgentMail digest, and ingestion evidence in a read-only schedule.
- Every next-run field is honestly `unknown`; no schedule is inferred or registered.
- Stale is asserted only for the existing 48-hour backup contract. Other rows retain `expected cadence: unknown` and are not labelled overdue.
- Controlled stale-backup fixture test passed.
- Browser proof: `workflows/queue_artifacts/pass5-proof/browser-proof.json` and two screenshots.

Token usage: unavailable from current CLI output.
