"""STEP I3 -- remove the obsolete sources/historical_calls/MANIFEST.md from the live
Business Brain vault, using the same primitives the codebase already uses for vault writes
(tools.brain_memory's lock + git helpers, same Hermes author identity write_transaction
always commits as) and the same retrieval-refresh calls tools/source_intake.py already makes
after every gated write. write_transaction() has no delete primitive (established in STEP I2's
addendum, which used the identical git rm + commit pattern for its own misfiled-card cleanup) --
this is not a new mechanism, it is the same one reused for the one operation write_transaction
cannot express.

No model calls. No card/claim/INDEX regeneration. Only sources/historical_calls/MANIFEST.md is
touched in the vault.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dashboard.backend.business_brain_graph import BusinessBrainGraphService  # noqa: E402
from tools import aos_indexer, brain_memory  # noqa: E402
from tools.business_brain_scope import ClientScopeRegistry  # noqa: E402

VAULT = brain_memory.VAULT_ROOT
TARGET_RELATIVE = "sources/historical_calls/MANIFEST.md"
GRAPHIFY_ROOT = Path("/home/liam/graphify-brain")
SEARCH_DB = REPO_ROOT / "search/os_index.db"
REGISTRY_PATH = REPO_ROOT / "context/client_scope_registry.json"
SCHEMA_PATH = REPO_ROOT / "context/client_scope_registry.schema.json"


def main() -> None:
    target = VAULT / TARGET_RELATIVE
    if not target.is_file():
        report = {"status": "already-absent", "target": TARGET_RELATIVE}
        print(json.dumps(report, indent=2))
        return

    pre_sha256 = brain_memory.file_sha256(target)
    pre_head = brain_memory._git("rev-parse", "HEAD").stdout.strip()

    with brain_memory._transaction_lock():
        staged = [line for line in brain_memory._git("diff", "--cached", "--name-only").stdout.splitlines() if line]
        if staged:
            raise SystemExit(f"vault index already has staged changes, refusing to proceed: {staged}")

        brain_memory._git("rm", "--", TARGET_RELATIVE)
        brain_memory._git(
            "-c", f"user.name={brain_memory.HERMES_AUTHOR_NAME}",
            "-c", f"user.email={brain_memory.HERMES_AUTHOR_EMAIL}",
            "commit", "-m", "hermes: i3-remove-obsolete-manifest-from-live-brain",
        )
        post_head = brain_memory._git("rev-parse", "HEAD").stdout.strip()

    gate = ClientScopeRegistry(registry_path=REGISTRY_PATH, schema_path=SCHEMA_PATH)
    graph_result = BusinessBrainGraphService(graphify_root=GRAPHIFY_ROOT, vault_root=VAULT, registry=gate).build()
    # Deliberately NOT roots=[VAULT]: tools/source_intake.py narrows to roots=[brain_root]
    # after its own single-source writes, but this step is a general refresh, not a
    # single-source write -- scan()'s own default (roots=None -> [LIVE_ROOT, BUSINESS_BRAIN_ROOT])
    # is the one that actually reproduces the full, already-published index (4275 docs across
    # both agentic_os_live: and business_brain: scopes, confirmed before this run). Passing
    # roots=[VAULT] here would silently drop every agentic_os_live:-scoped row on publish.
    search_result = aos_indexer.scan(SEARCH_DB, registry=gate)

    conn = aos_indexer.connect(SEARCH_DB, readonly=True)
    try:
        manifest_rows = list(conn.execute(
            "SELECT path FROM documents WHERE path LIKE '%historical_calls/MANIFEST.md'"
        ))
        historical_rows = list(conn.execute(
            "SELECT path FROM documents WHERE path LIKE 'business_brain:sources/historical_calls/%' "
            "AND path NOT LIKE '%/cards/%'"
        ))
        card_rows = list(conn.execute(
            "SELECT path FROM documents WHERE path LIKE 'business_brain:sources/historical_calls/cards/%'"
        ))
    finally:
        conn.close()

    report = {
        "status": "removed",
        "target": TARGET_RELATIVE,
        "pre_removal_sha256": pre_sha256,
        "vault_head_before": pre_head,
        "vault_head_after": post_head,
        "graph_result_status": graph_result.get("status"),
        "search_result_status": search_result.get("status"),
        "search_result_published": search_result.get("published"),
        "manifest_indexed_after": [r[0] for r in manifest_rows],
        "historical_non_card_rows_after": sorted(r[0] for r in historical_rows),
        "historical_card_rows_after": sorted(r[0] for r in card_rows),
        "manifest_present_on_disk_after": target.is_file(),
        "rollback": f'git -C "{VAULT}" revert --no-edit {post_head}',
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
