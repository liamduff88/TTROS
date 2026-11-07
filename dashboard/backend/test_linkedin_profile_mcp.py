"""Read-only LinkedIn MCP: one parameterless operation, Access JWT + identity allowlist, mocked provider."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_PRE_IMPORT_PATH = list(sys.path)
_PRE_IMPORT_MODULES = set(sys.modules)
sys.path.insert(0, str(TOOLS_DIR))

import httpx2
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import linkedin_profile_mcp
import shared_brain_http

# Same isolation as test_shared_brain_stage1: do not leave tools/ modules cached under bare names.
sys.path[:] = _PRE_IMPORT_PATH
for _name in set(sys.modules) - _PRE_IMPORT_MODULES:
    _file = getattr(sys.modules[_name], "__file__", None) or ""
    if "." not in _name and Path(_file).parent == TOOLS_DIR and _name not in {"linkedin_profile_mcp", "shared_brain_http"}:
        del sys.modules[_name]

BASE = "https://brain.timetorevenue.com"
URL = f"{BASE}/api/brain/linkedin/"
PROFILE = {"data": {"name": "Liam Duff", "email": "liamduff88@gmail.com", "access_token": "should-not-leave"}, "successful": True}
IDENTITIES = {"valid-liam": "liamduff88@gmail.com", "valid-work": "liam@timetorevenue.com", "valid-other": "someone@example.com"}
LIVE_ALLOWLIST = "liamduff88@gmail.com,liam@timetorevenue.com"


def _verify(value):
    return IDENTITIES.get(value)


class InstallFlagTest(unittest.TestCase):
    def test_disabled_by_default_mounts_nothing(self):
        app = FastAPI()
        with patch.dict(os.environ, {"TTROS_LINKEDIN_MCP_HTTP": ""}):
            self.assertFalse(linkedin_profile_mcp.install(app, Mock()))
        self.assertFalse(any(getattr(route, "path", "") == linkedin_profile_mcp.MOUNT_PATH for route in app.routes))

    def test_only_one_parameterless_tool_and_fixed_action(self):
        server = linkedin_profile_mcp._server(Mock())
        tools = server._tool_manager.list_tools()
        self.assertEqual([tool.name for tool in tools], ["linkedin_get_my_profile"])
        self.assertEqual(tools[0].parameters.get("properties", {}), {})
        self.assertEqual(linkedin_profile_mcp.ALLOWED_ACTION, "LINKEDIN_GET_MY_INFO")


class DirectCallTest(unittest.TestCase):
    def test_scrubs_secret_keys_and_fails_closed_on_adapter_error(self):
        runner = Mock(return_value={"ok": True, "result": PROFILE})
        result = linkedin_profile_mcp.get_my_profile(runner, "liamduff88@gmail.com")
        runner.assert_called_once_with("tool-run", "LINKEDIN_GET_MY_INFO", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["profile"]["data"]["access_token"], "[redacted]")
        self.assertEqual(result["profile"]["data"]["name"], "Liam Duff")
        for failure in ({"ok": False, "error": "x"}, "not a dict", None):
            self.assertFalse(linkedin_profile_mcp.get_my_profile(Mock(return_value=failure), "x")["success"])
        self.assertFalse(linkedin_profile_mcp.get_my_profile(Mock(side_effect=RuntimeError("boom")), "x")["success"])
        huge = {"ok": True, "result": {"blob": "x" * (linkedin_profile_mcp.MAX_RESULT_CHARS + 1)}}
        self.assertFalse(linkedin_profile_mcp.get_my_profile(Mock(return_value=huge), "x")["success"])


class HttpBoundaryTest(unittest.TestCase):
    def test_auth_refusals_and_single_allowlisted_read(self):
        runner = Mock(return_value={"ok": True, "result": PROFILE})

        async def run():
            app = FastAPI()
            with patch.dict(os.environ, {"TTROS_LINKEDIN_MCP_HTTP": "1", "TTROS_LINKEDIN_MCP_IDENTITIES": "liamduff88@gmail.com"}):
                self.assertTrue(linkedin_profile_mcp.install(app, runner))
                with patch.object(shared_brain_http, "verify_access_jwt", side_effect=_verify):
                    async with app.router.lifespan_context(app):
                        transport = httpx2.ASGITransport(app=app)
                        async with httpx2.AsyncClient(transport=transport, base_url=BASE) as http:
                            self.assertEqual((await http.post("/api/brain/linkedin/", json={})).status_code, 401)
                            self.assertEqual((await http.post("/api/brain/linkedin/", json={}, headers={"Cf-Access-Jwt-Assertion": "forged"})).status_code, 401)
                            self.assertEqual((await http.post("/api/brain/linkedin/", json={}, headers={"Cf-Access-Jwt-Assertion": "valid-other"})).status_code, 403)
                            # The MCP trusts only the verified Access JWT: Dashboard/Tailscale-style headers do nothing.
                            for forged in ({"Tailscale-User-Login": "liamduff88@gmail.com", "X-TTROS-Remote-PC": "1"},
                                           {"Cf-Access-Authenticated-User-Email": "liamduff88@gmail.com"},
                                           {"X-Forwarded-User": "liamduff88@gmail.com"}):
                                self.assertEqual((await http.post("/api/brain/linkedin/", json={}, headers=forged)).status_code, 401)
                            runner.assert_not_called()
                            http.headers["Cf-Access-Jwt-Assertion"] = "valid-liam"
                            async with streamable_http_client(URL, http_client=http) as streams:
                                async with ClientSession(*streams) as session:
                                    await session.initialize()
                                    tools = (await session.list_tools()).tools
                                    self.assertEqual([tool.name for tool in tools], ["linkedin_get_my_profile"])
                                    for name, args in (("tool_run", {"tool_slug": "LINKEDIN_CREATE_LINKED_IN_POST"}),
                                                       ("search", {"query": "x"})):
                                        self.assertTrue((await session.call_tool(name, args)).is_error)
                                    runner.assert_not_called()
                                    result = (await session.call_tool(
                                        "linkedin_get_my_profile", {"tool_slug": "LINKEDIN_CREATE_LINKED_IN_POST", "text": "hi"})).structured_content
                                    ok = (await session.call_tool("linkedin_get_my_profile", {})).structured_content
            return result, ok

        injected, result = asyncio.run(run())
        # Extra arguments are ignored or rejected, never forwarded: every call that reached the
        # adapter used the fixed action with empty arguments.
        self.assertTrue(all(call.args == ("tool-run", "LINKEDIN_GET_MY_INFO", {}) for call in runner.call_args_list), runner.call_args_list)
        self.assertGreaterEqual(runner.call_count, 1)
        self.assertLessEqual(runner.call_count, 2)
        self.assertTrue(result["success"])
        self.assertEqual(result["profile"]["data"]["access_token"], "[redacted]")
        self.assertNotIn("should-not-leave", str(injected))


class DiscoveryIdentityTest(unittest.TestCase):
    """ChatGPT authenticated through Access as liam@timetorevenue.com and got 403 before initialize."""

    def _discover(self, allowlist: str, assertion: str):
        runner = Mock()

        async def run():
            app = FastAPI()
            with patch.dict(os.environ, {"TTROS_LINKEDIN_MCP_HTTP": "1", "TTROS_LINKEDIN_MCP_IDENTITIES": allowlist}):
                self.assertTrue(linkedin_profile_mcp.install(app, runner))
                with patch.object(shared_brain_http, "verify_access_jwt", side_effect=_verify):
                    async with app.router.lifespan_context(app):
                        transport = httpx2.ASGITransport(app=app)
                        async with httpx2.AsyncClient(transport=transport, base_url=BASE) as http:
                            statuses = {name: (await http.post(URL, json={}, headers=headers)).status_code
                                        for name, headers in (("none", {}), ("forged", {"Cf-Access-Jwt-Assertion": "forged"}),
                                                              ("other", {"Cf-Access-Jwt-Assertion": "valid-other"}),
                                                              ("caller", {"Cf-Access-Jwt-Assertion": assertion}))}
                            if statuses["caller"] == 403:
                                return statuses, None
                            http.headers["Cf-Access-Jwt-Assertion"] = assertion
                            async with streamable_http_client(URL, http_client=http) as streams:
                                async with ClientSession(*streams) as session:
                                    await session.initialize()
                                    return statuses, [tool.name for tool in (await session.list_tools()).tools]

        result = asyncio.run(run())
        runner.assert_not_called()
        return result

    def test_old_allowlist_refuses_work_identity(self):
        statuses, tools = self._discover("liamduff88@gmail.com", "valid-work")
        self.assertEqual(statuses["caller"], 403)
        self.assertIsNone(tools)

    def test_live_allowlist_discovers_exactly_one_tool_for_both_identities(self):
        for assertion in ("valid-work", "valid-liam"):
            statuses, tools = self._discover(LIVE_ALLOWLIST, assertion)
            self.assertEqual(tools, ["linkedin_get_my_profile"], assertion)
            self.assertEqual((statuses["none"], statuses["forged"], statuses["other"]), (401, 401, 403))


if __name__ == "__main__":
    unittest.main()
