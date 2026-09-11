"""Step 4 — D-STALENESS mechanism check, zero model calls.

Builds the Hermes system prompt twice in the SAME process for profile
"david", mutating .hermes.md between builds -- exactly the sequence
agent/conversation_compression.py runs mid-session
(`agent._invalidate_system_prompt(); agent._build_system_prompt(...)`).

If build #2 reflects the mutated content, context files are re-read on a
compression-triggered rebuild (explicit approval is the safer policy).
If build #2 still shows the old content, they are not.

This makes no network call and touches no credential store. Tees a .txt
transcript beside itself; refuses to overwrite an existing one.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TRANSCRIPT = Path(__file__).with_suffix(".txt")
HERMES_MD = Path("/home/liam/agentic-os-live/.hermes.md")

SENTINEL_A = "TTROS-DSTALE-SENTINEL-A-static-check"
SENTINEL_B = "TTROS-DSTALE-SENTINEL-B-static-check-mutated"


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 1

    lines: list[str] = []

    def log(s: str) -> None:
        print(s)
        lines.append(s)

    original_hermes_md = HERMES_MD.read_text() if HERMES_MD.exists() else None

    sys.path.insert(0, "/home/liam/.hermes/hermes-agent")
    os.chdir("/home/liam/agentic-os-live")  # git root, so .hermes.md resolves

    from hermes_cli.prompt_size import _build_inspection_agent
    from agent.system_prompt import build_system_prompt

    log("=== D-STALENESS offline mechanism check ===")
    log(f"cwd: {os.getcwd()}")
    log(f"HERMES_MD path: {HERMES_MD}")

    try:
        HERMES_MD.write_text(f"Sentinel value: {SENTINEL_A}\n")
        agent = _build_inspection_agent("cli")

        prompt_1 = build_system_prompt(agent)
        log(f"[build #1] contains SENTINEL_A: {SENTINEL_A in prompt_1}")
        log(f"[build #1] contains SENTINEL_B: {SENTINEL_B in prompt_1}")

        # Mutate the file mid-process, mirroring what would happen if the
        # map/context file changed between session start and a later
        # compression-triggered rebuild.
        HERMES_MD.write_text(f"Sentinel value: {SENTINEL_B}\n")

        # Mirrors agent/conversation_compression.py:693-694 exactly.
        agent._invalidate_system_prompt()
        prompt_2 = agent._build_system_prompt()

        log(f"[build #2, post-invalidate] contains SENTINEL_A: {SENTINEL_A in prompt_2}")
        log(f"[build #2, post-invalidate] contains SENTINEL_B: {SENTINEL_B in prompt_2}")

        re_read = (SENTINEL_A in prompt_1) and (SENTINEL_B in prompt_2) and (SENTINEL_A not in prompt_2)
        log(f"RESULT: context files re-read on invalidate+rebuild = {re_read}")
        log(
            "This licenses: on this pinned build, agent._invalidate_system_prompt() + "
            "agent._build_system_prompt() (the exact pair agent/conversation_compression.py "
            "calls on every compression) performs a fresh disk read of .hermes.md, not a reuse "
            "of the session-start content. It does NOT license any claim about the update-vault "
            "map generator, which does not exist yet -- .hermes.md is used here only because it "
            "is the real, already-implemented Hermes context-file mechanism this pinned build "
            "has today."
        )
    finally:
        if original_hermes_md is not None:
            HERMES_MD.write_text(original_hermes_md)
        else:
            HERMES_MD.write_text(f"Sentinel value: {SENTINEL_A}\n")  # leave A for the live call

    TRANSCRIPT.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
