# aos-marketing
> Revisit: when marketing profile configuration or authentication changes. · Last touched: 2026-07-31.

Purpose: LinkedIn drafts, positioning, founder voice, website copy, and thought leadership.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Identity/model/tool prompt loading passes offline;
live inference is blocked by HTTP 401 from stale profile-scoped credentials.
Fail visibly; never fall back to `default` or change auth inside queue routing.

Escalation note: escalate core positioning, public founder voice, offer messaging, or repeated revision to Operating Hermes.
