"""Focused Stage 1 Shared Brain transport, bounds and refusal checks."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_PRE_IMPORT_PATH = list(sys.path)
_PRE_IMPORT_MODULES = set(sys.modules)
sys.path.insert(0, str(TOOLS_DIR))

import httpx2
import jwt
from fastapi import FastAPI
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import aos_entity_index
import aos_indexer
import shared_brain_http
import shared_brain_read

# Pytest imports every test module before running any. Leaving tools/ on sys.path, or its
# modules cached under bare names, makes tools.brain_memory_mcp bind a second brain_memory
# that tests patching tools.brain_memory cannot reach.
sys.path[:] = _PRE_IMPORT_PATH
for _name in set(sys.modules) - _PRE_IMPORT_MODULES:
    _file = getattr(sys.modules[_name], "__file__", None) or ""
    if "." not in _name and Path(_file).parent == TOOLS_DIR:
        del sys.modules[_name]


class ReadContractTests(unittest.TestCase):
    def test_baseline_search_and_entity(self):
        for query in ("TTROS", "Liam", "Shared Brain", "Graphify", "Memory Exchange"):
            direct = aos_indexer.search(query, source="business_brain", limit=3, client_scope="global")
            expected = [row["path"] for group in direct["groups"].values() for row in group]
            actual = [row["reference"] for row in shared_brain_read.search(query, 3)["matches"]]
            self.assertEqual(actual, expected)
            self.assertTrue(all(len(row["snippet"]) <= 300 for row in shared_brain_read.search(query, 3)["matches"]))
        for query in ("Liam", "Kenneth"):
            aos_entity_index.ensure_current()
            direct = aos_entity_index.search_entities(query, limit=10)
            actual = shared_brain_read.entity(query)
            self.assertEqual(actual["entities"], direct["entities"])
            self.assertLessEqual(len(json.dumps(actual, ensure_ascii=False)), 8_000)

    def test_read_index_boundary_and_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brain"
            root.mkdir()
            outside = Path(tmp) / "outside.md"
            outside.write_text("outside")
            (root / "long.md").write_text("x" * 20_005)
            (root / "escape.md").symlink_to(outside)
            db = Path(tmp) / "index.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE documents (path TEXT, source TEXT, client_scope TEXT)")
            for name in ("long.md", "escape.md", "sessions/hidden.md"):
                conn.execute("INSERT INTO documents VALUES (?, ?, ?)", ("business_brain:" + name, "business_brain", "global"))
            conn.commit()
            conn.close()
            with patch.object(shared_brain_read, "VAULT_ROOT", root), patch.object(aos_indexer, "runtime_db_path", return_value=db):
                for reference in ("..", "/etc/passwd", "business_brain:escape.md", "business_brain:unknown.md", "business_brain:sessions/hidden.md"):
                    self.assertFalse(shared_brain_read.read(reference)["success"], reference)
                first = shared_brain_read.read("business_brain:long.md")
                self.assertEqual(len(first["content"]), 20_000)
                self.assertEqual(first["next_offset"], 20_000)
                second = shared_brain_read.read("business_brain:long.md", first["next_offset"])
                self.assertEqual(second["content"], "x" * 5)
                self.assertIsNone(second["next_offset"])

    def test_access_jwt_signature_audience_and_expiry(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_client = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key()))
        issuer = "https://timetorevenue.cloudflareaccess.com"
        import time
        base = {"iss": issuer, "aud": "brain-audience", "email": "verified@example.com", "exp": int(time.time()) + 60}
        with patch.dict(os.environ, {"TTROS_BRAIN_ACCESS_AUTH_DOMAIN": "timetorevenue.cloudflareaccess.com", "TTROS_BRAIN_ACCESS_AUD": "brain-audience"}), patch.dict(shared_brain_http._jwk_clients, {"timetorevenue.cloudflareaccess.com": key_client}):
            self.assertEqual(shared_brain_http.verify_access_jwt(jwt.encode(base, private, algorithm="RS256")), "verified@example.com")
            self.assertIsNone(shared_brain_http.verify_access_jwt("malformed"))
            self.assertIsNone(shared_brain_http.verify_access_jwt(jwt.encode({**base, "aud": "wrong"}, private, algorithm="RS256")))
            self.assertIsNone(shared_brain_http.verify_access_jwt(jwt.encode({**base, "exp": int(time.time()) - 1}, private, algorithm="RS256")))


class HttpContractTests(unittest.TestCase):
    def test_install_logs_served_tools_per_address(self):
        for enabled, tools in ((False, "search,read,entity"), (True, "search,read,entity,checkpoint,resume")):
            with patch.object(shared_brain_http, "WRITE_ENABLED", enabled), \
                 self.assertLogs(shared_brain_http._log, level="INFO") as logs:
                shared_brain_http.install(FastAPI())
            self.assertEqual([line for line in logs.output if "shared_brain mount" in line],
                             [f"INFO:ttros.shared_brain:shared_brain mount surface={surface} tools={tools}"
                              for surface in ("claude", "chatgpt")])

    def test_stage2_attribution_and_write_flag(self):
        with patch.object(shared_brain_http, "WRITE_ENABLED", False):
            self.assertEqual([tool.name for tool in shared_brain_http._server()._tool_manager.list_tools()],
                             ["search", "read", "entity"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brain"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            stamp = {"authenticated_identity": "verified@example.com", "surface": "claude",
                     "actor_class": "authorised_client", "surface_source": "address"}
            fields = {"goal": "Continue", "done": "First step", "decisions": "One note",
                      "work_product_reference": "https://example.com/work", "next_action": "Next step",
                      "open_questions": "None", "surface": "chatgpt", "authenticated_identity": "spoofed"}
            token = shared_brain_http._attribution.set(stamp)
            try:
                with patch.object(shared_brain_http.shared_brain_checkpoint, "VAULT_ROOT", root), \
                     patch.object(shared_brain_http.shared_brain_checkpoint, "_mirror", return_value="test_only"):
                    result = shared_brain_http._call("checkpoint", workstream_id="http-workstream",
                                                     fields=fields, expected_version=0)
                self.assertTrue(result["success"], result)
                self.assertEqual({key: result["note"][key] for key in stamp}, stamp)
            finally:
                shared_brain_http._attribution.reset(token)

    def test_server_stamped_call_is_logged(self):
        stamp = {
            "authenticated_identity": "verified@example.com",
            "surface": "claude",
            "actor_class": "authorised_client",
            "surface_source": "address",
        }
        token = shared_brain_http._attribution.set(stamp)
        try:
            with patch.object(shared_brain_http._log, "info") as log_info:
                result = shared_brain_http._call("search", query="Liam", limit=1)
            self.assertTrue(result["success"])
            self.assertEqual(log_info.call_args.args[1:], ("search", *stamp.values()))
        finally:
            shared_brain_http._attribution.reset(token)

    def test_mcp_and_host_boundary(self):
        async def run():
            app = FastAPI()
            with patch.object(shared_brain_http, "WRITE_ENABLED", True):
                shared_brain_http.install(app)
            with patch.object(shared_brain_http, "verify_access_jwt", side_effect=lambda value: "test@example.com" if value == "valid" else None):
                async with app.router.lifespan_context(app):
                    transport = httpx2.ASGITransport(app=app)
                    async with httpx2.AsyncClient(transport=transport, base_url="https://brain.timetorevenue.com") as http:
                        self.assertEqual((await http.get("/api/brain/claude/")).status_code, 401)
                        self.assertEqual((await http.get("/api/health", headers={"Cf-Access-Jwt-Assertion": "valid"})).status_code, 404)
                        http.headers["Cf-Access-Jwt-Assertion"] = "valid"
                        async with streamable_http_client("https://brain.timetorevenue.com/api/brain/claude/", http_client=http) as streams:
                            async with ClientSession(*streams) as session:
                                init = await session.initialize()
                                self.assertEqual(init.instructions, shared_brain_read.CLIENT_INSTRUCTIONS)
                                tools = (await session.list_tools()).tools
                                self.assertEqual([tool.name for tool in tools], ["search", "read", "entity", "checkpoint", "resume"])
                                self.assertTrue(all("READ:" in tool.description for tool in tools[:3]))
                                self.assertEqual(tools[3].description, shared_brain_read.CHECKPOINT_GUIDANCE)
                                self.assertIn(shared_brain_read.CHECKPOINT_GUIDANCE, init.instructions)
                                self.assertIn("RESUME:", tools[4].description)
                                for query in ("TTROS", "Liam", "Shared Brain", "Graphify", "Memory Exchange"):
                                    result = (await session.call_tool("search", {"query": query, "limit": 3})).structured_content
                                    self.assertEqual(result["matches"], shared_brain_read.search(query, 3)["matches"])
                                reference = shared_brain_read.search("Liam", 1)["matches"][0]["reference"]
                                result = (await session.call_tool("read", {"reference": reference})).structured_content
                                self.assertEqual(result["reference"], reference)
                                for query in ("Liam", "Kenneth"):
                                    result = (await session.call_tool("entity", {"query_or_id": query})).structured_content
                                    self.assertEqual(result["entities"], shared_brain_read.entity(query)["entities"])
                                    for entity_id in [row["entity_id"] for row in result["entities"]]:
                                        view = (await session.call_tool("entity", {"query_or_id": entity_id})).structured_content
                                        self.assert_matches_entity_view(entity_id, view)
        asyncio.run(run())

    def assert_matches_entity_view(self, entity_id, response):
        """S1-3: the HTTP view is entity_view() itself, cut only by the 8,000-character bound."""
        direct = aos_entity_index.entity_view(entity_id)
        view, omitted = response["view"], response["omitted"]
        self.assertTrue(response["success"])
        self.assertLessEqual(len(json.dumps(response, ensure_ascii=False)), 8_000)
        self.assertEqual(set(view), set(direct) - {"token_usage_text"})
        for field, value in direct.items():
            if field == "token_usage_text":
                continue
            if not isinstance(value, list):
                self.assertEqual(view[field], value, field)
                continue
            if field in ("knowledge", "sources", "timeline", "import_dated"):
                value = [row for row in value if shared_brain_read._indexed_target(str(row.get("path") or ""))]
            self.assertEqual(view[field], value[:len(view[field])], field)
            self.assertEqual(len(view[field]) + omitted.get(field, 0), len(value), field)

    def test_entity_view_bound_refuses_to_hide_truncation(self):
        """[must refuse] A view cut to the bound must report what it dropped."""
        response = shared_brain_read.entity("person:liam-duff")
        self.assertGreater(sum(response["omitted"].values()), 0)
        response["omitted"] = {}
        with self.assertRaises(AssertionError):
            self.assert_matches_entity_view("person:liam-duff", response)


if __name__ == "__main__":
    unittest.main()
