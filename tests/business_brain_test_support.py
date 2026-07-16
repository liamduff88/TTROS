import json
from pathlib import Path

from business_brain_scope import ClientScopeRegistry


ROOT = Path(__file__).resolve().parents[1]


def write_note(path: Path, note_id: str, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nid: {note_id}\ntype: knowledge\n---\n# {title}\n\n{body}\n", encoding="utf-8")


def registry_data(*, include_global_repo: bool = True) -> dict:
    repo_rules = [{"source": "agentic_os_live", "path_prefix": "agentic_os_live:"}] if include_global_repo else []
    return {
        "schema_version": 1,
        "default_deny": True,
        "global_scope_id": "global",
        "denied_brain_pointers": ["business_brain:memory/protected.md"],
        "scopes": {
            "global": {
                "kind": "global", "enabled": True,
                "brain_pointers": ["business_brain:README.md", "business_brain:index/MEMORY_INDEX.md", "business_brain:memory/global.md"],
                "search_source_identities": repo_rules + [{"source": "business_brain", "paths": ["business_brain:README.md", "business_brain:index/MEMORY_INDEX.md", "business_brain:memory/global.md"]}],
                "graphify_targets": [{"namespace": "ttros-business-brain", "paths": ["business_brain:README.md", "business_brain:index/MEMORY_INDEX.md", "business_brain:memory/global.md"]}],
                "evidence_identities": ["proof:block-2:accepted-block-1", "proof:block-2:deterministic-write", "proof:block-2:later-retrieval"]
            },
            "client-a": {
                "kind": "client", "enabled": True,
                "brain_pointers": ["business_brain:memory/client-a.md"],
                "search_source_identities": [{"source": "business_brain", "paths": ["business_brain:memory/client-a.md"]}],
                "graphify_targets": [{"namespace": "ttros-business-brain", "paths": ["business_brain:memory/client-a.md"]}],
                "evidence_identities": ["thread:client-a:1", "proof:client-a"]
            },
            "client-b": {
                "kind": "client", "enabled": True,
                "brain_pointers": ["business_brain:memory/client-b.md"],
                "search_source_identities": [{"source": "business_brain", "paths": ["business_brain:memory/client-b.md"]}],
                "graphify_targets": [{"namespace": "ttros-business-brain", "paths": ["business_brain:memory/client-b.md"]}],
                "evidence_identities": ["thread:client-b:1", "proof:client-b"]
            },
            "client-disabled": {
                "kind": "client", "enabled": False, "brain_pointers": [],
                "search_source_identities": [], "graphify_targets": [], "evidence_identities": []
            }
        }
    }


def make_registry(data: dict | None = None) -> ClientScopeRegistry:
    return ClientScopeRegistry(
        data=data or registry_data(),
        schema_path=ROOT / "context" / "client_scope_registry.schema.json",
    )


def write_registry(path: Path, data: dict | None = None) -> ClientScopeRegistry:
    value = data or registry_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return ClientScopeRegistry(registry_path=path, schema_path=ROOT / "context" / "client_scope_registry.schema.json")
