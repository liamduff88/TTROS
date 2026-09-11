#!/usr/bin/env python3
"""One-time gated Business Brain write: file canonical memory/career.md for
Step 5 / D4 (career entry, class 9 of the approved manifest).

Goes through tools.brain_memory.write_transaction exclusively -- no editor
tool, no redirect, no sed. Refuses to overwrite an existing transcript.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools import brain_memory  # noqa: E402

SESSION_ID = "claude-code-session-step5-d4-career-filing-20260906"
SOURCE = "ttros-step5-d4-manifest-approval-2026-09-06"

CAREER_MD = """---
id: ttros-brain-career
type: knowledge
---
# Career

Liam is actively pursuing consulting and digital-strategy roles alongside building Time to Revenue.

Career, income and job-search context are in scope for David as part of the broader personal executive-assistant role.

Availability is not execution:

- Durable career context may remain available to David.
- Dated interviews, application deadlines and follow-up commitments surface through normal priorities/commitments.
- Job searching or applications execute only on Liam's explicit request, an active task/goal, or a deadline requiring action.
- Never launch recurring or background job searches automatically.

TTR remains active alongside the career search; do not imply that the career search replaces TTR.
"""

TRANSCRIPT = Path(__file__).with_suffix(".txt")


def main() -> int:
    if TRANSCRIPT.exists():
        print(f"REFUSING TO OVERWRITE existing transcript: {TRANSCRIPT}")
        return 1

    lines = []

    def log(msg: str) -> None:
        print(msg)
        lines.append(msg)

    log("=== Step 5 D4 -- gated write of memory/career.md ===")
    log(f"vault root: {brain_memory.VAULT_ROOT}")
    existing_hash = brain_memory.file_sha256(brain_memory._target("memory/career.md"))
    log(f"pre-write hash (None if file does not exist yet): {existing_hash}")

    try:
        result = brain_memory.write_transaction(
            {"memory/career.md": CAREER_MD},
            source=SOURCE,
            session_id=SESSION_ID,
        )
    except brain_memory.BrainMemoryError as exc:
        log(f"WRITE FAILED: {exc}")
        TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    log(f"changed_paths: {result.changed_paths}")
    log(f"commit: {result.commit}")
    log(f"session_id: {result.session_id}")
    log(f"source: {result.source}")
    log(f"validation: {result.validation}")

    post_path = brain_memory._target("memory/career.md")
    post_hash = brain_memory.file_sha256(post_path)
    log(f"post-write hash: {post_hash}")
    post_text = post_path.read_text(encoding="utf-8")
    log(f"post-write byte length: {len(post_text.encode('utf-8'))}")
    log("post-write content follows:")
    log("-----BEGIN-----")
    log(post_text)
    log("-----END-----")

    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
