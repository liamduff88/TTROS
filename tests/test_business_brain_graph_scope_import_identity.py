"""STEP X4 Part D(a) regression coverage for the STEP X3 root cause.

dashboard/backend/business_brain_graph.py used to bare-import ``business_brain_scope``
(pushing its own tools/ directory onto sys.path first), while every other caller reached
from the Hermes-hook subprocess (tools/context_assembler.py, tools/business_brain_context.py)
only ever resolves the qualified ``tools.business_brain_scope`` name. Python caches modules
by exact import string, so the two spellings became two distinct module objects with two
distinct ``ClientScopeError`` classes whenever nothing had already aliased them in
sys.modules -- exactly the situation inside the Hermes-hook subprocess, where no test or
hook-shim import runs first. business_brain_graph.py's own ``except ClientScopeError``
(written to skip an out-of-scope graph node) then failed to catch what it was raised,
because it was bound to the wrong class.

These tests exercise the real classes and the real graph-module code path (not a
reimplementation), so they fail against the STEP X3 preimage (bare import) and pass once
the import is corrected to prefer the qualified module.
"""

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tools.business_brain_scope import ClientScopeError as QualifiedClientScopeError
from tools.business_brain_scope import ClientScopeRegistry as QualifiedClientScopeRegistry
from tests.business_brain_test_support import registry_data


class BusinessBrainGraphScopeImportIdentityTest(unittest.TestCase):
    def test_graph_module_client_scope_error_is_the_qualified_class(self):
        bbg = importlib.import_module("dashboard.backend.business_brain_graph")
        self.assertIs(
            bbg.ClientScopeError,
            QualifiedClientScopeError,
            "dashboard/backend/business_brain_graph.py's ClientScopeError must be the same "
            "class object as tools.business_brain_scope.ClientScopeError -- otherwise its own "
            "'except ClientScopeError' clause is bound to a second, distinct copy of the class "
            "and silently fails to catch an out-of-scope graph node (STEP X3 root cause).",
        )

    def test_out_of_scope_graph_target_is_caught_the_way_add_candidate_catches_it(self):
        """Reproduces the exact live failure: querying the graph with a global scope for a
        pointer under sources/intake/, which validate_graph_target() correctly refuses."""
        bbg = importlib.import_module("dashboard.backend.business_brain_graph")
        gate = QualifiedClientScopeRegistry(
            data=registry_data(),
            schema_path=ROOT / "context" / "client_scope_registry.schema.json",
        )
        caught = False
        try:
            gate.validate_graph_target(
                "global", "ttros-business-brain", "business_brain:sources/intake/INDEX.md",
            )
        except bbg.ClientScopeError:
            caught = True
        except QualifiedClientScopeError:
            self.fail(
                "the exception raised is a tools.business_brain_scope.ClientScopeError but "
                "business_brain_graph.py's own except clause did not catch it -- this is the "
                "STEP X3 module-identity split reproduced live."
            )
        self.assertTrue(caught, "validate_graph_target() did not raise for an out-of-scope pointer")


if __name__ == "__main__":
    unittest.main()
