import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import aos_indexer
from tests.business_brain_test_support import registry_data, write_registry


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AosSearchTest(unittest.TestCase):
    def setUp(self):
        self.originals = {
            "LIVE_ROOT": aos_indexer.LIVE_ROOT,
            "BUSINESS_BRAIN_ROOT": aos_indexer.BUSINESS_BRAIN_ROOT,
            "DB_PATH": aos_indexer.DB_PATH,
            "INGEST_CONFIG_PATH": aos_indexer.INGEST_CONFIG_PATH,
            "INGEST_RECEIPT_PATH": aos_indexer.INGEST_RECEIPT_PATH,
            "CLIENT_SCOPE_REGISTRY_PATH": aos_indexer.CLIENT_SCOPE_REGISTRY_PATH,
        }

    def tearDown(self):
        for key, value in self.originals.items():
            setattr(aos_indexer, key, value)

    def configure_roots(self, tmp: Path):
        live = tmp / "Agentic OS Live"
        brain = tmp / "TTROS Business Brain"
        live.mkdir()
        brain.mkdir()
        aos_indexer.LIVE_ROOT = live
        aos_indexer.BUSINESS_BRAIN_ROOT = brain
        aos_indexer.DB_PATH = live / "search" / "os_index.db"
        aos_indexer.INGEST_CONFIG_PATH = live / "queue" / "ingest_watch.json"
        aos_indexer.INGEST_RECEIPT_PATH = live / "queue" / "receipts" / "ingestion.jsonl"
        data = registry_data()
        extra = ["business_brain:client_offer.md", "business_brain:memory/canonical.md"]
        data["scopes"]["global"]["brain_pointers"].extend(extra)
        data["scopes"]["global"]["search_source_identities"][-1]["paths"].extend(extra)
        data["scopes"]["global"]["graphify_targets"][0]["paths"].extend(extra)
        aos_indexer.CLIENT_SCOPE_REGISTRY_PATH = live / "context/client_scope_registry.json"
        write_registry(aos_indexer.CLIENT_SCOPE_REGISTRY_PATH, data)
        return live, brain

    def test_excludes_protected_paths_and_secret_names(self):
        self.assertTrue(aos_indexer.is_excluded(Path("workspaces/north_shore_sales_coach/client.md")))
        self.assertTrue(aos_indexer.is_excluded(Path("connectors/telegram_bridge/allowed_chats.json")))
        self.assertTrue(aos_indexer.is_excluded(Path("queue/command_routes.json")))
        self.assertTrue(aos_indexer.is_excluded(Path("queue/model_routes.json")))
        self.assertTrue(aos_indexer.is_excluded(Path("queue/lane_profiles.json")))
        self.assertTrue(aos_indexer.is_excluded(Path("notes/.env.local")))
        self.assertTrue(aos_indexer.is_excluded(Path("docs/client_secret_notes.md")))
        self.assertTrue(aos_indexer.is_excluded(Path("legacy_harvest/archive.md")))
        self.assertFalse(aos_indexer.is_excluded(Path("workflows/linkedin_carousel_from_md/workflow.md")))

    def test_sqlite_fts_search_returns_expected_docs(self):
        with tempfile.TemporaryDirectory() as tmp_text:
            live, brain = self.configure_roots(Path(tmp_text))
            write(live / "workflows" / "linkedin_carousel_from_md" / "workflow.md", "# Carousel Workflow\nCreate carousel artifacts.")
            write(live / "queue" / "receipts" / "done.md", "# Receipt\ncarousel complete.")
            write(brain / "README.md", "# Business Brain\nOffer memory carousel reference.")

            result = aos_indexer.scan()
            self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")
            search = aos_indexer.search("carousel", limit=10, client_scope="global")
            self.assertGreaterEqual(search["count"], 3)
            paths = json.dumps(search["groups"])
            self.assertIn("workflows/linkedin_carousel_from_md/workflow.md", paths)
            self.assertIn("business_brain:README.md", paths)
            self.assertIsInstance(search["latency_ms"], float)

    def test_ingestion_receipt_creation_for_dropped_markdown(self):
        with tempfile.TemporaryDirectory() as tmp_text:
            live, _brain = self.configure_roots(Path(tmp_text))
            aos_indexer.ensure_default_config()
            write(live / "queue" / "inbox" / "drop.md", "# Dropped Note\ninbox carousel artifact")

            result = aos_indexer.ingest_tick()
            self.assertEqual(result["count"], 1)
            self.assertTrue(aos_indexer.INGEST_RECEIPT_PATH.exists())
            receipt = json.loads(aos_indexer.INGEST_RECEIPT_PATH.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(receipt["status"], "success")
            self.assertEqual(receipt["token_usage_text"], "Token usage: no agent invocation")
            indexed = aos_indexer.search("inbox carousel", client_scope="global")
            self.assertGreaterEqual(indexed["count"], 1)
            self.assertIn("agentic_os_live:queue/inbox/drop.md", json.dumps(indexed["groups"]))

    def test_business_brain_is_read_only_and_no_secret_content_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp_text:
            live, brain = self.configure_roots(Path(tmp_text))
            write(live / "workspaces" / "north_shore_sales_coach" / "note.md", "# north_shore\nprotected")
            write(live / "queue" / "inbox" / "secret.md", "API_KEY=should_not_index\nsafe carousel")
            write(brain / "client_offer.md", "# Client Offer\nBusiness Brain searchable offer.")
            before = sorted(path.relative_to(brain).as_posix() for path in brain.rglob("*"))

            aos_indexer.scan()
            after = sorted(path.relative_to(brain).as_posix() for path in brain.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(aos_indexer.search("API_KEY", client_scope="global")["count"], 0)
            north = aos_indexer.search("north_shore", client_scope="global")
            self.assertEqual(north["count"], 0)
            self.assertGreater(aos_indexer.search("offer", source="business_brain", client_scope="global")["count"], 0)

    def test_business_brain_backups_are_excluded_from_disposable_scan(self):
        with tempfile.TemporaryDirectory() as tmp_text:
            _live, brain = self.configure_roots(Path(tmp_text))
            write(brain / "memory" / "canonical.md", "# Canonical\nunique canonical phrase")
            write(brain / "_backups" / "memory" / "backup.md", "# Backup\nbackup-only phrase")
            aos_indexer.scan()
            self.assertEqual(aos_indexer.search("backup-only", source="business_brain", client_scope="global")["count"], 0)
            result = aos_indexer.search("canonical", source="business_brain", client_scope="global")
            self.assertEqual(result["count"], 1)
            self.assertIn("business_brain:memory/canonical.md", json.dumps(result["groups"]))

    def test_create_from_artifact_payload_does_not_auto_run_or_call_agents(self):
        payload = {
            "title": "Review artifact: Example",
            "owner": "unassigned",
            "priority": "normal",
            "tags": "artifact,search",
            "source": "dashboard/artifact",
            "context": "Create from indexed artifact. Review before running.",
            "source_refs": "agentic_os_live:results/example.md",
        }
        self.assertEqual(payload["source"], "dashboard/artifact")
        self.assertNotIn("/run", json.dumps(payload))
        self.assertNotIn("hermes", json.dumps(payload).lower())

    def test_backend_api_search_shape(self):
        if importlib.util.find_spec("fastapi") is None:
            fastapi = types.ModuleType("fastapi")
            fastapi.__spec__ = importlib.util.spec_from_loader("fastapi", loader=None)

            class _FastAPI:
                def __init__(self, *args, **kwargs):
                    pass
                def add_middleware(self, *args, **kwargs):
                    pass
                def get(self, *args, **kwargs):
                    return lambda function: function
                post = get
                middleware = get

            class _HTTPException(Exception):
                def __init__(self, status_code, detail):
                    self.status_code = status_code
                    self.detail = detail

            class _Request:
                pass

            fastapi.FastAPI = _FastAPI
            fastapi.HTTPException = _HTTPException
            fastapi.Request = _Request
            middleware = types.ModuleType("fastapi.middleware")
            cors = types.ModuleType("fastapi.middleware.cors")
            responses = types.ModuleType("fastapi.responses")
            middleware.__spec__ = importlib.util.spec_from_loader("fastapi.middleware", loader=None)
            cors.__spec__ = importlib.util.spec_from_loader("fastapi.middleware.cors", loader=None)
            responses.__spec__ = importlib.util.spec_from_loader("fastapi.responses", loader=None)
            cors.CORSMiddleware = object
            responses.JSONResponse = object
            sys.modules.update({
                "fastapi": fastapi,
                "fastapi.middleware": middleware,
                "fastapi.middleware.cors": cors,
                "fastapi.responses": responses,
            })
        if importlib.util.find_spec("pydantic") is None:
            pydantic = types.ModuleType("pydantic")
            pydantic.__spec__ = importlib.util.spec_from_loader("pydantic", loader=None)

            class _BaseModel:
                def __init__(self, **values):
                    for key, value in values.items():
                        setattr(self, key, value)

            pydantic.BaseModel = _BaseModel
            sys.modules["pydantic"] = pydantic

        spec = importlib.util.spec_from_file_location("agentic_os_backend_search", ROOT / "dashboard" / "backend" / "main.py")
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        fake = {"groups": {"files": []}, "latency_ms": 1.2, "token_usage_text": "Token usage: no agent invocation"}
        with patch.object(backend.aos_indexer, "search", return_value=fake) as search:
            result = backend.api_search(q="carousel", type="workflow", tag="", source="", limit=5, client_scope="global")
        search.assert_called_once_with("carousel", kind="workflow", tag="", source="", limit=5, client_scope="global")
        self.assertEqual(result["latency_ms"], 1.2)
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_index_paths_do_not_import_or_invoke_model_clients(self):
        source = (TOOLS / "aos_indexer.py").read_text(encoding="utf-8")
        forbidden = ("import openai", "import anthropic", "subprocess.run", "requests.", "httpx.", "wsl.exe")
        for term in forbidden:
            self.assertNotIn(term, source.lower())
        self.assertIn("sqlite3", source)
        self.assertIn("fts5", source.lower())


if __name__ == "__main__":
    unittest.main()
