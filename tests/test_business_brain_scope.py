import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from business_brain_context import BrainContextError, ScopedBrainLoader, ThreadEvidenceFixtureLoader, validate_brain_context_used
from business_brain_scope import ClientScopeError
from tests.business_brain_test_support import make_registry, write_note


class BusinessBrainScopeTest(unittest.TestCase):
    def fixture(self, root: Path):
        write_note(root / "memory/client-a.md", "note-a", "Client A", "SENTINEL-A")
        write_note(root / "memory/client-b.md", "note-b", "Client B", "SENTINEL-B")
        write_note(root / "memory/global.md", "note-global", "Global", "GLOBAL-SENTINEL")
        write_note(root / "README.md", "note-root", "Root", "Root navigation")
        write_note(root / "index/MEMORY_INDEX.md", "note-index", "Index", "Index navigation")
        write_note(root / "memory/protected.md", "note-protected", "Protected", "PROTECTED-SENTINEL")

    def test_pointer_scope_is_checked_before_opener(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            self.fixture(vault)
            opened = []
            loader = ScopedBrainLoader(registry=make_registry(), vault_root=vault, opener=lambda path: opened.append(path) or path.read_text())
            result = loader.retrieve(work={"client_scope": "client-a"}, pointers=["business_brain:memory/client-a.md"])
            self.assertEqual(result.brain_context_used[0]["note_id"], "note-a")
            self.assertEqual(result.brain_context_used[0]["retrieval_route"], "pointer")
            with self.assertRaises(ClientScopeError):
                loader.retrieve(work={"client_scope": "client-a"}, pointers=["business_brain:memory/client-b.md"])
            self.assertEqual([path.name for path in opened], ["client-a.md"])

    def test_missing_disabled_conflicting_global_and_protected_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            self.fixture(vault)
            opened = []
            loader = ScopedBrainLoader(registry=make_registry(), vault_root=vault, opener=lambda path: opened.append(path) or path.read_text())
            for scope, pointer in (
                (None, "business_brain:memory/client-a.md"),
                ("client-disabled", "business_brain:memory/client-a.md"),
                ("client-a", "business_brain:memory/client-b.md"),
                ("client-a", "business_brain:memory/global.md"),
                ("global", "business_brain:memory/protected.md"),
                ("global", "business_brain:_backups/old.md"),
            ):
                with self.assertRaises((ClientScopeError, ValueError)):
                    loader.retrieve(work={"client_scope": scope}, pointers=[pointer])
            self.assertEqual(opened, [])
            global_result = loader.retrieve(work={"client_scope": "global"}, pointers=["business_brain:memory/global.md"])
            self.assertIn("GLOBAL-SENTINEL", global_result.contents[0])

    def test_thread_evidence_scope_gate_precedes_fixture_deserialization(self):
        calls = []
        loader = ThreadEvidenceFixtureLoader(make_registry())
        self.assertEqual(loader.load(client_scope="client-a", evidence_identity="thread:client-a:1", loader=lambda identity: calls.append(identity) or {"id": identity}), {"id": "thread:client-a:1"})
        with self.assertRaises(ClientScopeError):
            loader.load(client_scope="client-a", evidence_identity="thread:client-b:1", loader=lambda identity: calls.append(identity))
        with self.assertRaises(ClientScopeError):
            loader.load(client_scope=None, evidence_identity="thread:client-a:1", loader=lambda identity: calls.append(identity))
        self.assertEqual(calls, ["thread:client-a:1"])

    def test_receipt_context_rejects_cross_client_and_unopened_records(self):
        valid = {"note_id": "note-a", "path": "business_brain:memory/client-a.md", "client_scope": "client-a", "retrieval_route": "pointer"}
        self.assertEqual(len(validate_brain_context_used([valid], client_scope="client-a", registry=make_registry())), 1)
        with self.assertRaises(BrainContextError):
            validate_brain_context_used([{**valid, "client_scope": "client-b"}], client_scope="client-a", registry=make_registry())
        with self.assertRaises((BrainContextError, ClientScopeError)):
            validate_brain_context_used([{**valid, "path": "business_brain:memory/client-b.md"}], client_scope="client-a", registry=make_registry())


if __name__ == "__main__":
    unittest.main()
