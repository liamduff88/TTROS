"""One live LINKEDIN_GET_MY_INFO read through real install() + production adapter command. Budget: 1 call."""
import asyncio, json, os, shlex, subprocess, sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path("/home/liam/agentic-os-live"); sys.path.insert(0, str(ROOT / "tools"))
OUT = Path(__file__).with_name("live_read.txt")
if OUT.exists() and "--overwrite" not in sys.argv: sys.exit("refusing to overwrite live_read.txt")
import httpx2
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import linkedin_profile_mcp, shared_brain_http
MAX_CALLS, calls, log = 1, [], []
def runner(mode, subject, args):  # identical command shape to main._run_composio_adapter
    if len(calls) >= MAX_CALLS: raise SystemExit("live-call budget exceeded")
    calls.append((mode, subject, args))
    cmd = 'export PATH="$HOME/.local/npm/bin:$HOME/.local/bin:$HOME/.composio:$PATH"; ' + f"cd {shlex.quote(str(ROOT))}; python3 connectors/composio_access_adapter.py {shlex.quote(mode)} {shlex.quote(subject)} {shlex.quote(json.dumps(args, separators=(',', ':')))}"
    r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=120)
    try: return json.loads(r.stdout.strip() or r.stderr.strip())
    except json.JSONDecodeError: return {"ok": False, "error": "non-json"}
async def main():
    app = FastAPI()
    with patch.dict(os.environ, {"TTROS_LINKEDIN_MCP_HTTP": "1", "TTROS_LINKEDIN_MCP_IDENTITIES": "liamduff88@gmail.com"}):
        assert linkedin_profile_mcp.install(app, runner)
        with patch.object(shared_brain_http, "verify_access_jwt", side_effect={"t-liam": "liamduff88@gmail.com", "t-other": "x@example.com"}.get):
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="https://brain.timetorevenue.com") as http:
                    log.append(f"no-JWT status={(await http.post('/api/brain/linkedin/', json={})).status_code}")
                    log.append(f"non-allowlisted status={(await http.post('/api/brain/linkedin/', json={}, headers={'Cf-Access-Jwt-Assertion': 't-other'})).status_code}")
                    http.headers["Cf-Access-Jwt-Assertion"] = "t-liam"
                    async with streamable_http_client("https://brain.timetorevenue.com/api/brain/linkedin/", http_client=http) as s:
                        async with ClientSession(*s) as session:
                            await session.initialize()
                            tools = (await session.list_tools()).tools
                            log.append(f"tools={[t.name for t in tools]} count={len(tools)} input_properties={tools[0].input_schema.get('properties', {})}")
                            res = (await session.call_tool("linkedin_get_my_profile", {})).structured_content
    prof = res.get("profile") or {}
    inner = prof.get("data", prof) if isinstance(prof, dict) else {}
    log.append(f"success={res.get('success')} action={res.get('action')} error={res.get('error')}")
    log.append(f"profile_keys={sorted(inner.keys()) if isinstance(inner, dict) else type(inner).__name__}")
    log.append(f"adapter_calls={calls} live_calls={len(calls)} declared_max={MAX_CALLS}")
asyncio.run(main())
OUT.write_text("\n".join(log) + "\n"); print(OUT.read_text())
