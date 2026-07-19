# Decision — executable Codex context handoff
> Revisit: when Codex JSONL or context-window semantics change. · Last touched: 2026-07-19.

The configured 50% Codex boundary is enforced at 75,000 cumulative JSONL
tokens by both live subprocess constructors. The supervisor treats the final
cumulative usage event as a replacement snapshot, writes a compact
artifact-backed handoff, ends the current process, and continues through a new
`codex exec --ephemeral` process using only the handoff path. It never resumes
a transcript or enables same-session auto-compaction. Four successive
handoffs are the fail-closed maximum.

This standalone decision keeps the retained-context change merge-separable
from unrelated pre-existing edits in `decisions/DECISIONS.md`.
