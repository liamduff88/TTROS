"""Safe, deterministic Graphify repository ingest for the local dashboard.

No function in this module executes cloned repository content or invokes a model.
Revisit: when Graphify's CLI contract or repository-ingest threat model changes. · Last touched: 2026-07-13.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable


DEFAULT_BRAIN_ROOT = Path("/home/liam/graphify-brain")
DEFAULT_REPO_ROOT = Path("/home/liam/agentic-os-live")
CONTROLLED_PATH = "/home/liam/.local/bin:/home/liam/.local/npm/bin"
TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
COMPONENT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$")
APPROVED_ARTIFACTS = {
    "graphify-out/graph.html": "text/html; charset=utf-8",
    "graphify-out/GRAPH_TREE.html": "text/html; charset=utf-8",
    "graphify-out/GRAPH_REPORT.md": "text/markdown; charset=utf-8",
    "graphify-out/graph.json": "application/json",
    "PROVENANCE.md": "text/markdown; charset=utf-8",
    "INGEST_RECEIPT.json": "application/json",
    "QUARANTINE_SCAN.json": "application/json",
}
GRAPH_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src 'none'; connect-src 'none'; object-src 'none'; "
    "media-src 'none'; frame-src 'none'; worker-src 'none'; form-action 'none'; "
    "base-uri 'none'; frame-ancestors 'self'"
)


class GraphifyError(RuntimeError):
    """An honest, operator-readable ingest or Graphify failure."""


@dataclass(frozen=True)
class RepoIdentity:
    owner: str
    repository: str

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repository}"

    @property
    def key(self) -> str:
        return f"{self.owner}/{self.repository}"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%S%fZ")


def validate_github_url(value: str) -> RepoIdentity:
    """Accept exactly an HTTPS github.com owner/repository URL."""
    raw = str(value or "")
    if raw != raw.strip() or not raw or any(ord(char) > 127 for char in raw):
        raise GraphifyError("URL must be non-empty ASCII with no surrounding whitespace")
    if "\\" in raw or "\x00" in raw or any(ord(char) < 32 for char in raw):
        raise GraphifyError("URL contains a prohibited character")
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as exc:
        raise GraphifyError("URL is malformed") from exc
    if parsed.scheme != "https":
        raise GraphifyError("only https:// GitHub URLs are accepted")
    if parsed.netloc != "github.com" or parsed.hostname != "github.com":
        raise GraphifyError("host must be exactly github.com")
    if parsed.username is not None or parsed.password is not None:
        raise GraphifyError("embedded credentials are prohibited")
    try:
        if parsed.port is not None:
            raise GraphifyError("ports are prohibited")
    except ValueError as exc:
        raise GraphifyError("port is invalid") from exc
    if parsed.query or parsed.fragment:
        raise GraphifyError("query strings and fragments are prohibited")
    if "%" in parsed.path:
        raise GraphifyError("percent-encoded path components are prohibited")
    parts = parsed.path.split("/")
    if len(parts) != 3 or parts[0] != "" or not parts[1] or not parts[2]:
        raise GraphifyError("URL must contain exactly one owner and one repository component")
    owner, repository = parts[1], parts[2]
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not repository or repository in {".", ".."} or owner in {".", ".."}:
        raise GraphifyError("owner and repository must be non-empty safe components")
    if not COMPONENT_RE.fullmatch(owner) or not COMPONENT_RE.fullmatch(repository):
        raise GraphifyError("owner or repository contains unsupported characters")
    return RepoIdentity(owner=owner, repository=repository)


def validate_identity_component(value: str, label: str = "component") -> str:
    text = str(value or "")
    if not COMPONENT_RE.fullmatch(text) or text in {".", ".."}:
        raise GraphifyError(f"invalid repository {label}")
    return text


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _bounded_tail(value: str, limit: int = 12000) -> str:
    text = str(value or "")
    return text[-limit:]


def _safe_env() -> dict[str, str]:
    allowed = {key: os.environ[key] for key in ("HOME", "LANG", "LC_ALL", "TMPDIR", "TZ") if key in os.environ}
    allowed.update({
        "PATH": f"{CONTROLLED_PATH}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
    })
    return allowed


def clone_argv(source: str, destination: Path, *, allow_local_fixture: bool = False, git_bin: str = "git") -> list[str]:
    protocol = "always" if allow_local_fixture else "never"
    return [
        git_bin,
        "-c", f"protocol.file.allow={protocol}",
        "-c", "core.hooksPath=/dev/null",
        "-c", "init.templateDir=",
        "-c", "http.followRedirects=false",
        "clone",
        "--depth", "1",
        "--no-tags",
        "--single-branch",
        "--no-recurse-submodules",
        "--config", "core.hooksPath=/dev/null",
        "--", source, str(destination),
    ]


def run_git_clone(
    source: str,
    destination: Path,
    *,
    git_bin: str = "git",
    timeout: int = 180,
    allow_local_fixture: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    argv = clone_argv(source, destination, allow_local_fixture=allow_local_fixture, git_bin=git_bin)
    started = time.monotonic()
    result = runner(
        argv,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=_safe_env(),
        stdin=subprocess.DEVNULL,
    )
    record = {
        "argv": argv,
        "shell": False,
        "return_code": result.returncode,
        "stdout_tail": _bounded_tail(result.stdout),
        "stderr_tail": _bounded_tail(result.stderr),
        "duration_seconds": round(time.monotonic() - started, 3),
        "prompt_disabled": True,
        "authentication_disabled": True,
        "hooks_disabled": True,
        "shallow": True,
        "recursive_submodules": False,
        "redirects_disabled": True,
    }
    if result.returncode != 0:
        raise GraphifyError(f"safe shallow clone failed: {_bounded_tail(result.stderr, 2000) or 'git returned an error'}")
    return record


LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".c": "C", ".h": "C/C++", ".cpp": "C++",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
    ".html": "HTML", ".css": "CSS", ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
}
SCRIPT_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".ps1", ".rb", ".pl", ".php"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".whl", ".jar"}
PACKAGE_MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pom.xml", "build.gradle"}
LOCK_FILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock", "uv.lock", "Cargo.lock", "Gemfile.lock", "composer.lock"}
CONTAINER_FILES = {"Dockerfile", "Containerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", ".dockerignore"}
MAKEFILES = {"Makefile", "makefile", "GNUmakefile"}


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _symlink_escape(root: Path, path: Path, target: str) -> bool:
    candidate = Path(target) if os.path.isabs(target) else path.parent / target
    normalized = Path(os.path.abspath(os.path.normpath(str(candidate))))
    try:
        normalized.relative_to(root.resolve())
        return False
    except ValueError:
        return True


def quarantine_scan(root: Path, *, max_files: int = 50000, max_directories: int = 10000, max_depth: int = 64, max_total_size: int = 2_000_000_000, sample_bytes: int = 8192) -> dict[str, Any]:
    """Inspect a clone using lstat/scandir only; never follow symlinks or special files."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise GraphifyError("quarantine root is not a directory")
    extensions: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    largest: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "root": str(root), "timestamp": iso_now(), "file_count": 0, "directory_count": 0,
        "total_size": 0, "extensions": {}, "languages": {}, "largest_files": largest,
        "executables": [], "binary_files": [], "archives": [], "script_files": [],
        "package_manifests": [], "lock_files": [], "container_files": [], "makefiles": [],
        "ci_configuration": [], "github_actions": [], "hooks_like_files": [],
        "submodule_declarations": [], "symlinks": [], "symlink_targets": [],
        "symlink_escape_targets": [], "unusual_filesystem_objects": [],
        "scan_limits": {"max_files": max_files, "max_directories": max_directories, "max_depth": max_depth, "max_total_size": max_total_size, "sample_bytes": sample_bytes},
        "skipped_files": 0, "skipped_directories": 0, "warnings": [], "limits_hit": [],
    }
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    stop_files = False
    while queue:
        directory, depth = queue.popleft()
        if depth > max_depth:
            result["skipped_directories"] += 1
            result["limits_hit"].append("max_depth")
            continue
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            result["warnings"].append(f"cannot scan {_relative(root, directory) or '.'}: {exc.__class__.__name__}")
            result["skipped_directories"] += 1
            continue
        for entry in entries:
            path = Path(entry.path)
            relative = _relative(root, path)
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                result["warnings"].append(f"cannot lstat {relative}: {exc.__class__.__name__}")
                result["skipped_files"] += 1
                continue
            mode = info.st_mode
            if stat.S_ISLNK(mode):
                try:
                    target = os.readlink(path)
                except OSError as exc:
                    target = f"<unreadable:{exc.__class__.__name__}>"
                    result["warnings"].append(f"cannot read symlink {relative}")
                link = {"path": relative, "target": target, "escape": not target.startswith("<") and _symlink_escape(root, path, target)}
                result["symlinks"].append(link)
                result["symlink_targets"].append({"path": relative, "target": target})
                if link["escape"]:
                    result["symlink_escape_targets"].append(link)
                continue
            if stat.S_ISDIR(mode):
                if result["directory_count"] >= max_directories:
                    result["skipped_directories"] += 1
                    result["limits_hit"].append("max_directories")
                    continue
                result["directory_count"] += 1
                queue.append((path, depth + 1))
                continue
            if not stat.S_ISREG(mode):
                kind = "fifo" if stat.S_ISFIFO(mode) else "socket" if stat.S_ISSOCK(mode) else "device" if stat.S_ISCHR(mode) or stat.S_ISBLK(mode) else "unknown"
                result["unusual_filesystem_objects"].append({"path": relative, "type": kind})
                continue
            if stop_files or result["file_count"] >= max_files:
                stop_files = True
                result["skipped_files"] += 1
                result["limits_hit"].append("max_files")
                continue
            if result["total_size"] + info.st_size > max_total_size:
                result["skipped_files"] += 1
                result["limits_hit"].append("max_total_size")
                continue
            result["file_count"] += 1
            result["total_size"] += info.st_size
            suffix = path.suffix.lower()
            extensions[suffix or "[none]"] += 1
            if suffix in LANGUAGES:
                languages[LANGUAGES[suffix]] += 1
            largest.append({"path": relative, "bytes": info.st_size})
            largest.sort(key=lambda row: (-row["bytes"], row["path"]))
            del largest[20:]
            name = path.name
            lower_rel = relative.lower()
            if mode & 0o111:
                result["executables"].append(relative)
            if suffix in ARCHIVE_EXTENSIONS:
                result["archives"].append(relative)
            if suffix in SCRIPT_EXTENSIONS:
                result["script_files"].append(relative)
            if name in PACKAGE_MANIFESTS:
                result["package_manifests"].append(relative)
            if name in LOCK_FILES or name.endswith(".lock"):
                result["lock_files"].append(relative)
            if name in CONTAINER_FILES or name.startswith("Dockerfile."):
                result["container_files"].append(relative)
            if name in MAKEFILES:
                result["makefiles"].append(relative)
            if lower_rel.startswith((".github/", ".gitlab/", ".circleci/")) or name in {"Jenkinsfile", ".travis.yml", "azure-pipelines.yml"}:
                result["ci_configuration"].append(relative)
            if lower_rel.startswith(".github/workflows/"):
                result["github_actions"].append(relative)
            if "/hooks/" in f"/{lower_rel}" or "hook" in name.lower():
                result["hooks_like_files"].append(relative)
            if name == ".gitmodules":
                result["submodule_declarations"].append(relative)
            try:
                with path.open("rb") as handle:
                    sample = handle.read(sample_bytes)
                if b"\x00" in sample:
                    result["binary_files"].append(relative)
                if sample.startswith(b"#!") and relative not in result["script_files"]:
                    result["script_files"].append(relative)
            except OSError as exc:
                result["warnings"].append(f"cannot sample {relative}: {exc.__class__.__name__}")
    result["extensions"] = dict(sorted(extensions.items()))
    result["languages"] = dict(sorted(languages.items()))
    result["limits_hit"] = sorted(set(result["limits_hit"]))
    result["validation_status"] = "warnings" if result["warnings"] or result["limits_hit"] else "pass"
    return result


def validate_graph_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GraphifyError("Graphify did not emit a parseable graph JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("nodes"), list):
        raise GraphifyError("graph JSON must be an object containing a nodes array")
    edges = value.get("edges", value.get("links", []))
    if not isinstance(edges, list):
        raise GraphifyError("graph JSON edges/links must be an array")
    return value


def discover_graphify_artifacts(output: Path) -> dict[str, Path]:
    candidates = sorted(path for path in output.rglob("graph.json") if path.is_file() and path.parent.name == "graphify-out")
    if len(candidates) != 1:
        raise GraphifyError(f"expected exactly one nested graphify-out/graph.json, found {len(candidates)}")
    graph_json = candidates[0]
    graph_dir = graph_json.parent
    return {
        "graph_json": graph_json,
        "graph_html": graph_dir / "graph.html",
        "report": graph_dir / "GRAPH_REPORT.md",
        "tree": graph_dir / "GRAPH_TREE.html",
        "graphify_tree_raw": graph_dir / "GRAPH_TREE.graphify.html",
    }


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def write_safe_graph_preview(graph: dict[str, Any], path: Path, label: str) -> None:
    payload = _json_for_script(graph)
    title = html.escape(label)
    document = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>__TITLE__ graph</title>
<style>
html,body{margin:0;height:100%;overflow:hidden;background:#111;color:#e8e0d0;font:13px system-ui}
body{display:grid;grid-template-rows:auto 1fr}
header{display:flex;align-items:center;gap:10px;min-height:42px;padding:7px 12px;border-bottom:1px solid #3a3936;background:#171716}
#stats{color:#c5a86c}.hint{color:#978e81;font-size:11px}.spacer{flex:1}
button{border:1px solid #4b4842;border-radius:4px;background:#22211f;color:#e8e0d0;padding:4px 9px;cursor:pointer}
button:hover,button:focus-visible{border-color:#c5a86c;outline:none}
#stage{position:relative;min-height:0}svg{display:block;width:100%;height:100%;cursor:grab;touch-action:none}
svg.panning{cursor:grabbing}.edge{stroke:#736b60;stroke-opacity:.34;transition:stroke-opacity .12s}.edge.related{stroke:#c5a86c;stroke-opacity:.9;stroke-width:1.8}.edge.dimmed{stroke-opacity:.07}
.node{cursor:pointer;outline:none}.node circle{fill:#c5a86c;stroke:#f0e6d2;stroke-width:.8;transition:opacity .12s,fill .12s,stroke-width .12s}.node text{fill:#e8e0d0;font-size:10px;pointer-events:none}.node:hover circle,.node:focus-visible circle,.node.connected circle{fill:#dfc98f;stroke-width:2}.node.selected circle{fill:#f2b84b;stroke:#fff;stroke-width:3}.node.dimmed{opacity:.18}
#details{position:absolute;right:12px;top:12px;width:min(310px,calc(100% - 36px));max-height:calc(100% - 48px);overflow:auto;border:1px solid #6a604e;border-radius:6px;background:rgba(23,23,22,.96);padding:12px;box-shadow:0 8px 24px #0008}
#details[hidden]{display:none}#details h2{margin:0 24px 9px 0;color:#f0e6d2;font-size:15px;overflow-wrap:anywhere}#details dl{display:grid;grid-template-columns:auto 1fr;gap:6px 10px;margin:0}#details dt{color:#978e81}#details dd{margin:0;overflow-wrap:anywhere}#close{position:absolute;right:7px;top:7px;padding:1px 7px}
#empty{position:absolute;left:14px;bottom:12px;color:#978e81;font-size:11px;pointer-events:none}
@media(max-width:650px){header{gap:6px;padding-inline:9px}.hint{display:none}.spacer{min-width:2px}button{padding-inline:7px}}
</style></head><body>
<header><strong>__TITLE__</strong><span id="stats">rendering</span><span class="hint">Click a node · drag to pan · scroll to zoom</span><span class="spacer"></span><button id="zoom-out" type="button" aria-label="Zoom out">−</button><button id="zoom-in" type="button" aria-label="Zoom in">+</button><button id="reset" type="button">Reset view</button></header>
<main id="stage"><svg id="graph" viewBox="0 0 1200 720" role="application" aria-label="Interactive repository dependency graph"><g id="viewport"><g id="edges"></g><g id="nodes"></g></g></svg><aside id="details" aria-live="polite" hidden><button id="close" type="button" aria-label="Close node details">×</button><h2 id="detail-title"></h2><dl id="detail-fields"></dl></aside><div id="empty">No node selected</div></main>
<script>
"use strict";
const data=__PAYLOAD__;
const all=Array.isArray(data.nodes)?data.nodes:[];
const nodes=all.slice(0,260);
const links=(Array.isArray(data.edges)?data.edges:Array.isArray(data.links)?data.links:[]).slice(0,800);
const svg=document.getElementById('graph');
const viewport=document.getElementById('viewport');
const edgeLayer=document.getElementById('edges');
const nodeLayer=document.getElementById('nodes');
const details=document.getElementById('details');
const empty=document.getElementById('empty');
const NS='http://www.w3.org/2000/svg';
const key=(node,index)=>String(node.id??node.key??node.name??node.label??index);
const label=(node,index)=>String(node.name??node.label??node.id??('node '+index));
const ids=new Map(nodes.map((node,index)=>[key(node,index),index]));
const point=index=>{const angle=(index/Math.max(1,nodes.length))*Math.PI*2;const ring=170+(index%5)*46;return {x:600+Math.cos(angle)*ring,y:360+Math.sin(angle)*ring}};
const points=nodes.map((_,index)=>point(index));
const renderedEdges=[];
for(const edge of links){
  const source=ids.get(String(edge.source??edge.from??edge.src??''));
  const target=ids.get(String(edge.target??edge.to??edge.dst??''));
  if(source===undefined||target===undefined)continue;
  const line=document.createElementNS(NS,'line');
  line.classList.add('edge');
  line.setAttribute('x1',points[source].x);line.setAttribute('y1',points[source].y);
  line.setAttribute('x2',points[target].x);line.setAttribute('y2',points[target].y);
  edgeLayer.appendChild(line);renderedEdges.push({source,target,line});
}
const nodeGroups=[];
nodes.forEach((node,index)=>{
  const {x,y}=points[index];
  const group=document.createElementNS(NS,'g');group.classList.add('node');group.setAttribute('role','button');group.setAttribute('tabindex','0');group.setAttribute('aria-label','Inspect '+label(node,index));
  const circle=document.createElementNS(NS,'circle');circle.setAttribute('cx',x);circle.setAttribute('cy',y);circle.setAttribute('r',index<40?7:5);
  const tip=document.createElementNS(NS,'title');tip.textContent=label(node,index);circle.appendChild(tip);group.appendChild(circle);
  if(index<36){const text=document.createElementNS(NS,'text');text.setAttribute('x',x+9);text.setAttribute('y',y+3);text.textContent=label(node,index).slice(0,34);group.appendChild(text)}
  group.addEventListener('click',event=>{event.stopPropagation();selectNode(index)});
  group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectNode(index)}});
  nodeLayer.appendChild(group);nodeGroups.push(group);
});
const addField=(term,value)=>{if(value===undefined||value===null||value==='')return;const dt=document.createElement('dt');dt.textContent=term;const dd=document.createElement('dd');dd.textContent=String(value);document.getElementById('detail-fields').append(dt,dd)};
function clearSelection(){nodeGroups.forEach(group=>group.classList.remove('selected','connected','dimmed'));renderedEdges.forEach(({line})=>line.classList.remove('related','dimmed'));details.hidden=true;empty.hidden=false}
function selectNode(index){
  const connected=new Set([index]);let relationshipCount=0;
  renderedEdges.forEach(edge=>{const related=edge.source===index||edge.target===index;edge.line.classList.toggle('related',related);edge.line.classList.toggle('dimmed',!related);if(related){connected.add(edge.source);connected.add(edge.target);relationshipCount+=1}});
  nodeGroups.forEach((group,nodeIndex)=>{group.classList.toggle('selected',nodeIndex===index);group.classList.toggle('connected',nodeIndex!==index&&connected.has(nodeIndex));group.classList.toggle('dimmed',!connected.has(nodeIndex))});
  const node=nodes[index]||{};document.getElementById('detail-title').textContent=label(node,index);const fields=document.getElementById('detail-fields');fields.replaceChildren();
  addField('Kind',node.type??node.kind??node.metadata?.kind);addField('File',node.source_file??node.file??node.path??node.source);addField('Location',node.source_location);addField('Language',node.language??node.metadata?.language);addField('Community',node.community);addField('Relationships',relationshipCount);addField('ID',key(node,index));
  details.hidden=false;empty.hidden=true;
}
document.getElementById('close').addEventListener('click',clearSelection);
svg.addEventListener('click',event=>{if(event.target===svg)clearSelection()});
let transform={x:0,y:0,scale:1};
const applyTransform=()=>viewport.setAttribute('transform',`translate(${transform.x} ${transform.y}) scale(${transform.scale})`);
const rootPoint=event=>{const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;return point.matrixTransform(svg.getScreenCTM().inverse())};
const zoomAt=(factor,center={x:600,y:360})=>{const next=Math.min(5,Math.max(.35,transform.scale*factor));const contentX=(center.x-transform.x)/transform.scale;const contentY=(center.y-transform.y)/transform.scale;transform={x:center.x-contentX*next,y:center.y-contentY*next,scale:next};applyTransform()};
svg.addEventListener('wheel',event=>{event.preventDefault();zoomAt(event.deltaY<0?1.16:1/1.16,rootPoint(event))},{passive:false});
let pan=null;
svg.addEventListener('pointerdown',event=>{if(event.button!==0||event.target.closest('.node'))return;pan={pointerId:event.pointerId,start:rootPoint(event),x:transform.x,y:transform.y};svg.setPointerCapture(event.pointerId);svg.classList.add('panning')});
svg.addEventListener('pointermove',event=>{if(!pan||pan.pointerId!==event.pointerId)return;const current=rootPoint(event);transform.x=pan.x+current.x-pan.start.x;transform.y=pan.y+current.y-pan.start.y;applyTransform()});
const endPan=event=>{if(!pan||pan.pointerId!==event.pointerId)return;pan=null;svg.classList.remove('panning')};
svg.addEventListener('pointerup',endPan);svg.addEventListener('pointercancel',endPan);
document.getElementById('zoom-in').addEventListener('click',()=>zoomAt(1.25));document.getElementById('zoom-out').addEventListener('click',()=>zoomAt(1/1.25));document.getElementById('reset').addEventListener('click',()=>{transform={x:0,y:0,scale:1};applyTransform();clearSelection()});
document.getElementById('stats').textContent=all.length+' nodes · '+renderedEdges.length+' displayed edges';
</script></body></html>""".replace("__TITLE__", title).replace("__PAYLOAD__", payload)
    _atomic_write(path, document)


def write_safe_tree_preview(graph: dict[str, Any], path: Path, label: str) -> None:
    nodes = graph.get("nodes", [])
    rows = []
    for index, node in enumerate(nodes[:800]):
        if not isinstance(node, dict):
            continue
        file_name = str(node.get("source_file") or node.get("file") or node.get("path") or node.get("source") or "[unlocated]")
        name = str(node.get("name") or node.get("label") or node.get("id") or f"node {index}")
        rows.append({"file": file_name, "name": name, "type": str(node.get("type") or node.get("kind") or "node")})
    payload = _json_for_script(rows)
    title = html.escape(label)
    document = f"""<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>{title} tree</title><style>html,body{{margin:0;min-height:100%;background:#111;color:#e8e0d0;font:13px system-ui}}header{{position:sticky;top:0;background:#111;padding:12px 16px;border-bottom:1px solid #3a3936}}main{{padding:12px 18px}}details{{border-left:1px solid #4b4842;margin:5px 0;padding-left:12px}}summary{{cursor:pointer;color:#c5a86c}}li{{margin:4px 0}}small{{color:#978e81}}</style></head><body><header><strong>{title}</strong> · <span id=\"stats\">tree</span></header><main id=\"tree\"></main><script>\"use strict\";const rows={payload};const groups=new Map;for(const row of rows){{const file=String(row.file||'[unlocated]');if(!groups.has(file))groups.set(file,[]);groups.get(file).push(row)}}const root=document.getElementById('tree');for(const [file,items] of [...groups].sort((a,b)=>a[0].localeCompare(b[0]))){{const d=document.createElement('details');d.open=groups.size<18;const s=document.createElement('summary');s.textContent=file+' ('+items.length+')';d.appendChild(s);const ul=document.createElement('ul');for(const item of items.slice(0,200)){{const li=document.createElement('li');li.textContent=item.name+' ';const sm=document.createElement('small');sm.textContent=item.type;li.appendChild(sm);ul.appendChild(li)}}d.appendChild(ul);root.appendChild(d)}}document.getElementById('stats').textContent=rows.length+' symbols · '+groups.size+' files';</script></body></html>"""
    _atomic_write(path, document)


def ensure_report(graph: dict[str, Any], path: Path, identity: RepoIdentity) -> None:
    if path.is_file() and path.stat().st_size:
        return
    edges = graph.get("edges", graph.get("links", []))
    content = "\n".join([
        f"# Graph Report — {identity.key}", "", "> Revisit: after the next explicit rebuild. · Last touched: " + utc_now().date().isoformat(), "",
        "Deterministic code-only Graphify extraction.", "", f"- Nodes: {len(graph.get('nodes', []))}", f"- Edges: {len(edges)}", f"- Canonical source: {identity.canonical_url}", f"- {TOKEN_USAGE_TEXT}", "",
    ])
    _atomic_write(path, content)


def artifact_relative_path(value: str) -> str:
    text = str(value or "")
    if not text or "\x00" in text or "\\" in text or "%" in text or "//" in text or text.startswith(("/", "~", "./")) or "/./" in text:
        raise GraphifyError("artifact path contains a prohibited encoding or separator")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise GraphifyError("artifact path is not canonical")
    canonical = pure.as_posix()
    if canonical not in APPROVED_ARTIFACTS:
        raise GraphifyError("artifact is not an approved Graphify/system output")
    return canonical


class GraphifyService:
    def __init__(self, *, brain_root: Path = DEFAULT_BRAIN_ROOT, repo_root: Path = DEFAULT_REPO_ROOT, graphify_bin: str = "/home/liam/.local/bin/graphify", git_bin: str = "git", ingest_script: Path | None = None):
        self.brain_root = Path(brain_root).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.clone_root = self.brain_root / "intake" / "cloned-repos"
        self.output_root = self.brain_root / "repo_graphs"
        self.receipt_root = self.brain_root / "receipts"
        self.graphify_bin = graphify_bin
        self.git_bin = git_bin
        self.ingest_script = ingest_script or self.repo_root / "tools" / "aos-graphify-ingest.sh"
        for directory in (self.clone_root, self.output_root, self.receipt_root):
            directory.mkdir(parents=True, exist_ok=True)

    def paths(self, identity: RepoIdentity) -> tuple[Path, Path]:
        owner = validate_identity_component(identity.owner, "owner")
        repository = validate_identity_component(identity.repository, "name")
        clone = self.clone_root / owner / repository
        output = self.output_root / owner / repository
        for base, path in ((self.clone_root, clone), (self.output_root, output)):
            try:
                path.relative_to(base)
            except ValueError as exc:
                raise GraphifyError("repository path escaped its canonical root") from exc
        return clone, output

    def _receipt_path(self, identity: RepoIdentity | None, operation: str, status: str) -> Path:
        name = f"{identity.owner}-{identity.repository}" if identity else "invalid-url"
        digest = uuid.uuid4().hex[:8]
        return self.receipt_root / f"{timestamp_slug()}-{name}-{operation}-{status}-{digest}.json"

    def _write_receipt(self, payload: dict[str, Any], path: Path) -> None:
        _atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _graphify_version(self) -> str:
        try:
            result = subprocess.run([self.graphify_bin, "--version"], shell=False, capture_output=True, text=True, timeout=5, check=False, env=_safe_env(), stdin=subprocess.DEVNULL)
            return (result.stdout or result.stderr).strip() or "unavailable"
        except (OSError, subprocess.SubprocessError):
            return "unavailable"

    def _commit_hash(self, clone: Path) -> str:
        result = subprocess.run([self.git_bin, "-C", str(clone), "rev-parse", "HEAD"], shell=False, capture_output=True, text=True, timeout=10, check=False, env=_safe_env(), stdin=subprocess.DEVNULL)
        commit = result.stdout.strip()
        if result.returncode or not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
            raise GraphifyError("could not verify cloned commit hash")
        return commit.lower()

    def _run_ingest_script(self, clone: Path, output: Path, identity: RepoIdentity) -> dict[str, Any]:
        argv = [str(self.ingest_script), str(clone), str(output), identity.key]
        started = time.monotonic()
        result = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=600, check=False, env=_safe_env(), stdin=subprocess.DEVNULL)
        record = {
            "argv": ["graphify", "extract", str(clone), "--code-only", "--out", str(output)],
            "wrapper_argv": argv,
            "shell": False,
            "return_code": result.returncode,
            "stdout_tail": _bounded_tail(result.stdout),
            "stderr_tail": _bounded_tail(result.stderr),
            "duration_seconds": round(time.monotonic() - started, 3),
            "graphify_version": self._graphify_version(),
            "code_only": True,
        }
        if result.returncode != 0:
            raise GraphifyError(f"Graphify extraction failed: {_bounded_tail(result.stderr or result.stdout, 3000)}")
        return record

    def _prepare_output(self, clone: Path, output: Path, identity: RepoIdentity, operation: str, receipt_path: Path) -> dict[str, Any]:
        scan = quarantine_scan(clone)
        scan_path = output / "QUARANTINE_SCAN.json"
        _atomic_write(scan_path, json.dumps(scan, indent=2, sort_keys=True) + "\n")
        extract = self._run_ingest_script(clone, output, identity)
        artifacts = discover_graphify_artifacts(output)
        graph = validate_graph_json(artifacts["graph_json"])
        emitted_html = artifacts["graph_html"]
        if emitted_html.exists():
            emitted_html.replace(emitted_html.with_name("graph.graphify.html"))
        emitted_tree = artifacts["graphify_tree_raw"]
        write_safe_graph_preview(graph, artifacts["graph_html"], identity.key)
        write_safe_tree_preview(graph, artifacts["tree"], identity.key)
        ensure_report(graph, artifacts["report"], identity)
        for required in (artifacts["graph_json"], artifacts["graph_html"], artifacts["report"], artifacts["tree"]):
            if not required.is_file() or required.stat().st_size == 0:
                raise GraphifyError(f"required Graphify artifact is missing: {required.name}")
        commit = self._commit_hash(clone)
        final_clone, final_output = self.paths(identity)
        relative = {key: path.relative_to(output).as_posix() for key, path in artifacts.items() if path.exists()}
        provenance = {
            "canonical_url": identity.canonical_url, "owner": identity.owner, "repository": identity.repository,
            "clone_commit_hash": commit, "operation": operation, "timestamp": iso_now(),
            "graphify_version": extract["graphify_version"], "graphify_command": extract["argv"],
            "graphify_mode": "extract --code-only", "code_only": True,
            "clone_destination": str(final_clone), "published_output_directory": str(final_output),
            "quarantine_scan_path": str(final_output / "QUARANTINE_SCAN.json"),
            "quarantine_summary": {key: scan[key] for key in ("file_count", "directory_count", "total_size", "validation_status", "warnings", "limits_hit")},
            "graph_json_path": str(final_output / relative["graph_json"]),
            "graph_html_path": str(final_output / relative["graph_html"]),
            "report_path": str(final_output / relative["report"]),
            "tree_path": str(final_output / relative["tree"]),
            "graphify_tree_raw_path": str(final_output / relative["graphify_tree_raw"]) if "graphify_tree_raw" in relative else "",
            "receipt_path": str(receipt_path), "validation_status": "pass", "token_usage_text": TOKEN_USAGE_TEXT,
            "extraction": extract, "discovered_artifact_paths": relative,
        }
        md_lines = [
            f"# Graphify provenance — {identity.key}", "", "> Revisit: after the next explicit fetch, re-fetch, or rebuild. · Last touched: " + utc_now().date().isoformat(), "",
        ] + [f"- {key.replace('_', ' ').title()}: `{json.dumps(value) if isinstance(value, (dict, list)) else value}`" for key, value in provenance.items()] + [""]
        _atomic_write(output / "PROVENANCE.md", "\n".join(md_lines))
        _atomic_write(output / "PROVENANCE.json", json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        return {"scan": scan, "artifacts": artifacts, "provenance": provenance, "extract": extract, "commit": commit}

    @staticmethod
    def _remove_failed(path: Path) -> None:
        if path.exists() or path.is_symlink():
            shutil.rmtree(path, ignore_errors=True) if path.is_dir() and not path.is_symlink() else path.unlink(missing_ok=True)

    def _publish(self, temporary_clone: Path | None, temporary_output: Path, final_clone: Path, final_output: Path, operation: str) -> None:
        stamp = timestamp_slug()
        moved_clone: Path | None = None
        moved_output: Path | None = None
        try:
            if operation == "re-fetch":
                if temporary_clone is None or not final_clone.is_dir() or not final_output.is_dir():
                    raise GraphifyError("re-fetch requires an existing repository and output")
                clone_history = temporary_clone / ".history" / stamp / "repository"
                clone_history.parent.mkdir(parents=True, exist_ok=True)
                final_clone.replace(clone_history)
                moved_clone = clone_history
            if final_output.exists():
                output_history = temporary_output / ".history" / stamp / "output"
                output_history.parent.mkdir(parents=True, exist_ok=True)
                final_output.replace(output_history)
                moved_output = output_history
            if temporary_clone is not None:
                final_clone.parent.mkdir(parents=True, exist_ok=True)
                temporary_clone.replace(final_clone)
            final_output.parent.mkdir(parents=True, exist_ok=True)
            temporary_output.replace(final_output)
        except Exception:
            if not final_output.exists() and moved_output and moved_output.exists():
                moved_output.replace(final_output)
            if operation == "re-fetch" and not final_clone.exists() and moved_clone and moved_clone.exists():
                moved_clone.replace(final_clone)
            raise

    def ingest(self, url: str, *, refetch: bool = False) -> dict[str, Any]:
        identity: RepoIdentity | None = None
        operation = "re-fetch" if refetch else "fetch"
        temporary_clone: Path | None = None
        temporary_output: Path | None = None
        try:
            identity = validate_github_url(url)
            final_clone, final_output = self.paths(identity)
            if refetch:
                if not final_clone.is_dir() or not final_output.is_dir():
                    raise GraphifyError("explicit re-fetch requires an existing published repository")
            elif final_clone.exists() or final_output.exists():
                raise GraphifyError("repository already exists; use the explicit repository-specific Re-fetch action")
            temporary_clone = Path(tempfile.mkdtemp(prefix=f".tmp-{identity.owner}-{identity.repository}-", dir=self.clone_root))
            temporary_output = Path(tempfile.mkdtemp(prefix=f".tmp-{identity.owner}-{identity.repository}-", dir=self.output_root))
            # mkdtemp creates the target; git requires it not to exist.
            temporary_clone.rmdir()
            clone_record = run_git_clone(identity.canonical_url, temporary_clone, git_bin=self.git_bin)
            receipt_path = self._receipt_path(identity, operation, "success")
            built = self._prepare_output(temporary_clone, temporary_output, identity, operation, receipt_path)
            self._publish(temporary_clone, temporary_output, final_clone, final_output, operation)
            temporary_clone = temporary_output = None
            payload = {
                "status": "success", "operation": operation, "timestamp": iso_now(), "repository": identity.key,
                "canonical_url": identity.canonical_url, "clone": clone_record, "provenance": built["provenance"],
                "validation_status": "pass", "token_usage_text": TOKEN_USAGE_TEXT,
            }
            self._write_receipt(payload, receipt_path)
            _atomic_write(final_output / "INGEST_RECEIPT.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
            return self.repository(identity)
        except Exception as exc:
            receipt_path = self._receipt_path(identity, operation, "failed")
            failure = {
                "status": "failed", "operation": operation, "timestamp": iso_now(),
                "repository": identity.key if identity else None,
                "canonical_url": identity.canonical_url if identity else None,
                "error": str(exc), "validation_status": "failed", "token_usage_text": TOKEN_USAGE_TEXT,
            }
            self._write_receipt(failure, receipt_path)
            if temporary_clone is not None:
                self._remove_failed(temporary_clone)
            if temporary_output is not None:
                self._remove_failed(temporary_output)
            if isinstance(exc, GraphifyError):
                raise
            raise GraphifyError(str(exc)) from exc

    def rebuild(self, owner: str, repository: str) -> dict[str, Any]:
        identity = RepoIdentity(validate_identity_component(owner, "owner"), validate_identity_component(repository, "name"))
        clone, final_output = self.paths(identity)
        temporary_output: Path | None = None
        try:
            if not clone.is_dir() or not final_output.is_dir():
                raise GraphifyError("rebuild requires an existing repository-specific clone and output")
            existing = self._read_provenance(final_output)
            if existing.get("owner") != identity.owner or existing.get("repository") != identity.repository or existing.get("clone_destination") != str(clone):
                raise GraphifyError("repository provenance does not match the requested rebuild identity")
            temporary_output = Path(tempfile.mkdtemp(prefix=f".tmp-{identity.owner}-{identity.repository}-", dir=self.output_root))
            receipt_path = self._receipt_path(identity, "rebuild", "success")
            built = self._prepare_output(clone, temporary_output, identity, "rebuild", receipt_path)
            self._publish(None, temporary_output, clone, final_output, "rebuild")
            temporary_output = None
            payload = {"status": "success", "operation": "rebuild", "timestamp": iso_now(), "repository": identity.key, "canonical_url": identity.canonical_url, "provenance": built["provenance"], "validation_status": "pass", "token_usage_text": TOKEN_USAGE_TEXT}
            self._write_receipt(payload, receipt_path)
            _atomic_write(final_output / "INGEST_RECEIPT.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
            return self.repository(identity)
        except Exception as exc:
            receipt_path = self._receipt_path(identity, "rebuild", "failed")
            self._write_receipt({"status": "failed", "operation": "rebuild", "timestamp": iso_now(), "repository": identity.key, "canonical_url": identity.canonical_url, "error": str(exc), "validation_status": "failed", "token_usage_text": TOKEN_USAGE_TEXT}, receipt_path)
            if temporary_output is not None:
                self._remove_failed(temporary_output)
            if isinstance(exc, GraphifyError):
                raise
            raise GraphifyError(str(exc)) from exc

    @staticmethod
    def _read_provenance(output: Path) -> dict[str, Any]:
        provenance_path = output / "PROVENANCE.json"
        try:
            info = provenance_path.lstat()
            if not stat.S_ISREG(info.st_mode) or provenance_path.is_symlink():
                raise GraphifyError("published repository provenance must be a non-symlink regular file")
            value = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GraphifyError("published repository provenance is missing or invalid") from exc
        if not isinstance(value, dict):
            raise GraphifyError("published repository provenance is invalid")
        return value

    def repository(self, identity: RepoIdentity) -> dict[str, Any]:
        clone, output = self.paths(identity)
        provenance = self._read_provenance(output)
        expected_graph = output / "graphify-out" / "graph.json"
        if provenance.get("graph_json_path") != str(expected_graph):
            raise GraphifyError("published graph path does not match repository output structure")
        graph_path, _ = self.artifact(identity.owner, identity.repository, "graphify-out/graph.json")
        graph = validate_graph_json(graph_path)
        edges = graph.get("edges", graph.get("links", []))
        scan_path, _ = self.artifact(identity.owner, identity.repository, "QUARANTINE_SCAN.json")
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
        artifact_urls = {name: f"/api/graphify/artifacts/{identity.owner}/{identity.repository}/{relative}" for name, relative in {
            "graph": "graphify-out/graph.html", "tree": "graphify-out/GRAPH_TREE.html", "report": "graphify-out/GRAPH_REPORT.md", "graph_json": "graphify-out/graph.json", "provenance": "PROVENANCE.md", "receipt": "INGEST_RECEIPT.json", "scan": "QUARANTINE_SCAN.json",
        }.items()}
        return {
            "id": identity.key, "owner": identity.owner, "repository": identity.repository,
            "canonical_url": identity.canonical_url, "clone_exists": clone.is_dir(), "output_exists": output.is_dir(),
            "commit_hash": provenance.get("clone_commit_hash"), "operation": provenance.get("operation"),
            "timestamp": provenance.get("timestamp"), "graphify_version": provenance.get("graphify_version"),
            "node_count": len(graph.get("nodes", [])), "edge_count": len(edges), "scan_summary": provenance.get("quarantine_summary", {}),
            "scan_details": scan, "artifacts": artifact_urls, "paths": {key: provenance.get(key) for key in ("graph_json_path", "graph_html_path", "report_path", "tree_path", "receipt_path", "clone_destination", "published_output_directory")},
            "token_usage_text": TOKEN_USAGE_TEXT,
        }

    def list_repositories(self) -> list[dict[str, Any]]:
        rows = []
        if not self.output_root.exists():
            return rows
        for owner_path in sorted(self.output_root.iterdir()):
            if not owner_path.is_dir() or owner_path.is_symlink() or not COMPONENT_RE.fullmatch(owner_path.name):
                continue
            for repo_path in sorted(owner_path.iterdir()):
                if not repo_path.is_dir() or repo_path.is_symlink() or not COMPONENT_RE.fullmatch(repo_path.name):
                    continue
                try:
                    rows.append(self.repository(RepoIdentity(owner_path.name, repo_path.name)))
                except (GraphifyError, OSError, KeyError, json.JSONDecodeError):
                    continue
        return sorted(rows, key=lambda row: str(row.get("timestamp") or ""), reverse=True)

    def artifact(self, owner: str, repository: str, relative_path: str) -> tuple[Path, str]:
        identity = RepoIdentity(validate_identity_component(owner, "owner"), validate_identity_component(repository, "name"))
        relative = artifact_relative_path(relative_path)
        _, output = self.paths(identity)
        provenance = self._read_provenance(output)
        if provenance.get("owner") != identity.owner or provenance.get("repository") != identity.repository or provenance.get("published_output_directory") != str(output):
            raise GraphifyError("artifact repository provenance mismatch")
        path = output / relative
        try:
            info = path.lstat()
        except OSError as exc:
            raise GraphifyError("artifact not found") from exc
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise GraphifyError("artifact must be a non-symlink regular file")
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(output.resolve(strict=True))
            resolved.relative_to(self.output_root.resolve(strict=True))
        except ValueError as exc:
            raise GraphifyError("artifact escaped the serving root") from exc
        return resolved, APPROVED_ARTIFACTS[relative]

    def action(self, owner: str, repository: str, action: str, inputs: dict[str, Any]) -> dict[str, Any]:
        identity = RepoIdentity(validate_identity_component(owner, "owner"), validate_identity_component(repository, "name"))
        _, output = self.paths(identity)
        provenance = self._read_provenance(output)
        graph, _ = self.artifact(identity.owner, identity.repository, "graphify-out/graph.json")
        expected = output / "graphify-out" / "graph.json"
        if provenance.get("graph_json_path") != str(expected) or graph != expected.resolve(strict=True):
            raise GraphifyError("repository graph path failed provenance validation")
        action = str(action or "").strip().lower()
        if action == "query":
            question = str(inputs.get("question") or "").strip()
            if not question or len(question) > 500:
                raise GraphifyError("query must contain 1 to 500 characters")
            budget = max(50, min(int(inputs.get("budget") or 1200), 2000))
            argv = [self.graphify_bin, "query", question, "--budget", str(budget), "--graph", str(graph)]
        elif action == "explain":
            node = str(inputs.get("node") or "").strip()
            if not node or len(node) > 300:
                raise GraphifyError("node must contain 1 to 300 characters")
            argv = [self.graphify_bin, "explain", node, "--graph", str(graph)]
        elif action == "affected":
            node = str(inputs.get("node") or "").strip()
            if not node or len(node) > 300:
                raise GraphifyError("node must contain 1 to 300 characters")
            depth = max(1, min(int(inputs.get("depth") or 2), 8))
            argv = [self.graphify_bin, "affected", node, "--depth", str(depth), "--graph", str(graph)]
        elif action == "path":
            source, target = str(inputs.get("source") or "").strip(), str(inputs.get("target") or "").strip()
            if not source or not target or len(source) > 300 or len(target) > 300:
                raise GraphifyError("path source and target must each contain 1 to 300 characters")
            argv = [self.graphify_bin, "path", source, target, "--graph", str(graph)]
        else:
            raise GraphifyError("unsupported deterministic Graphify action")
        started = time.monotonic()
        try:
            result = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=20, check=False, env=_safe_env(), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise GraphifyError("Graphify action exceeded the 20 second limit") from exc
        stdout, stderr = _bounded_tail(result.stdout, 50000), _bounded_tail(result.stderr, 12000)
        if result.returncode:
            raise GraphifyError(f"Graphify {action} failed: {stderr or stdout or 'unknown error'}")
        return {"action": action, "repository": identity.key, "argv": argv, "return_code": result.returncode, "output": stdout, "stderr": stderr, "duration_seconds": round(time.monotonic() - started, 3), "model_invoked": False, "token_usage_text": TOKEN_USAGE_TEXT}
