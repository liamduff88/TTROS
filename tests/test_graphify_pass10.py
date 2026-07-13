from __future__ import annotations

# Revisit: when Graphify ingest, serving, or sandbox contracts change. · Last touched: 2026-07-13.

import json
import os
import socket
import stat
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from dashboard.backend.graphify_service import (
    APPROVED_ARTIFACTS,
    GRAPH_CSP,
    GraphifyError,
    GraphifyService,
    RepoIdentity,
    artifact_relative_path,
    clone_argv,
    discover_graphify_artifacts,
    quarantine_scan,
    run_git_clone,
    validate_github_url,
    validate_graph_json,
    write_safe_graph_preview,
    write_safe_tree_preview,
)


class UrlValidationTests(unittest.TestCase):
    def test_valid_url_with_and_without_dot_git(self):
        expected = RepoIdentity("pallets", "itsdangerous")
        self.assertEqual(expected, validate_github_url("https://github.com/pallets/itsdangerous"))
        self.assertEqual(expected, validate_github_url("https://github.com/pallets/itsdangerous.git"))

    def test_every_prohibited_url_class(self):
        invalid = [
            "https://user:password@github.com/owner/repo", "https://github.com/owner/repo?q=1",
            "https://github.com/owner/repo#fragment", "https://www.github.com/owner/repo",
            "https://github.com.evil.test/owner/repo", "ssh://git@github.com/owner/repo",
            "git@github.com:owner/repo.git", "git://github.com/owner/repo", "file:///tmp/repo",
            "/tmp/repo", "https://github.com:443/owner/repo", "https://github.com./owner/repo",
            "https://githu\N{CYRILLIC SMALL LETTER BE}.com/owner/repo", "https://github.com//repo",
            "https://github.com/owner/", "https://github.com/owner/repo/extra",
            "https://github.com/owner/../repo", "https://github.com/owner/%2e%2e",
            "https://github.com/owner/repo%2fextra", "https://github.com/owner\\repo",
            "https://github.com/owner/repo\x00", " https://github.com/owner/repo",
            "https://github.com/owner/repo ", "https://github.com/owner/repo//",
        ]
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaises(GraphifyError):
                validate_github_url(value)


class CloneSafetyTests(unittest.TestCase):
    def test_clone_invocation_is_argv_shell_false_and_locked_down(self):
        completed = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        runner = mock.Mock(return_value=completed)
        destination = Path("/tmp/fixture-destination")
        record = run_git_clone("https://github.com/pallets/itsdangerous", destination, runner=runner)
        args, kwargs = runner.call_args
        argv = args[0]
        self.assertIsInstance(argv, list)
        self.assertFalse(kwargs["shell"])
        self.assertEqual("0", kwargs["env"]["GIT_TERMINAL_PROMPT"])
        self.assertEqual("/bin/false", kwargs["env"]["GIT_ASKPASS"])
        self.assertIn("core.hooksPath=/dev/null", argv)
        self.assertIn("init.templateDir=", argv)
        self.assertIn("http.followRedirects=false", argv)
        self.assertIn("--depth", argv)
        self.assertIn("--no-recurse-submodules", argv)
        self.assertNotIn("--recurse-submodules", argv)
        self.assertFalse(record["recursive_submodules"])

    def test_local_disposable_git_fixture_clone(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            (source / "safe.py").write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "safe.py"], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
            run_git_clone(str(source), target, allow_local_fixture=True)
            self.assertEqual("VALUE = 1\n", (target / "safe.py").read_text(encoding="utf-8"))
            self.assertFalse((target / ".gitmodules").exists())

    def test_redirect_refusal_against_local_server(self):
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()

            def log_message(self, *_args):
                return

        server = HTTPServer(("127.0.0.1", 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp, self.assertRaises(GraphifyError):
                run_git_clone(f"http://127.0.0.1:{server.server_port}/repo.git", Path(temp) / "clone", timeout=10)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

    def test_clone_argv_has_no_shell_or_cloned_code_execution_tools(self):
        argv = clone_argv("https://github.com/pallets/itsdangerous", Path("/tmp/repo"))
        forbidden = {"bash", "sh", "npm", "pip", "pytest", "make", "docker", "podman"}
        self.assertTrue(forbidden.isdisjoint(argv))
        self.assertEqual("--", argv[-3])


class QuarantineTests(unittest.TestCase):
    def test_symlinks_are_classified_without_following_and_escape_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "regular.py").write_text("print('not executed')\n", encoding="utf-8")
            (root / "inside").mkdir()
            (root / "inside" / "ok.txt").write_text("ok", encoding="utf-8")
            (root / "broken").symlink_to("missing")
            (root / "absolute").symlink_to("/etc/passwd")
            (root / "escape").symlink_to("../../outside")
            (root / "safe-link").symlink_to("inside/ok.txt")
            scan = quarantine_scan(root)
            self.assertEqual(4, len(scan["symlinks"]))
            self.assertEqual({"absolute", "escape"}, {row["path"] for row in scan["symlink_escape_targets"]})
            self.assertNotIn("/etc/passwd", scan["binary_files"])

    def test_unusual_objects_and_scan_limits_are_honest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.mkfifo(root / "named-pipe")
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(root / "socket"))
            try:
                for index in range(8):
                    (root / f"file-{index}.txt").write_text(str(index), encoding="utf-8")
                scan = quarantine_scan(root, max_files=2)
            finally:
                sock.close()
            self.assertEqual({"fifo", "socket"}, {row["type"] for row in scan["unusual_filesystem_objects"]})
            self.assertEqual(2, scan["file_count"])
            self.assertGreater(scan["skipped_files"], 0)
            self.assertIn("max_files", scan["limits_hit"])

    def test_inventory_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
            for name in ("package.json", "package-lock.json", "Dockerfile", "Makefile", ".gitmodules", "run.sh", "archive.zip"):
                path = root / name
                path.write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "run.sh").chmod(0o755)
            scan = quarantine_scan(root)
            self.assertIn("package.json", scan["package_manifests"])
            self.assertIn("package-lock.json", scan["lock_files"])
            self.assertIn("Dockerfile", scan["container_files"])
            self.assertIn("Makefile", scan["makefiles"])
            self.assertIn(".github/workflows/ci.yml", scan["github_actions"])
            self.assertIn(".gitmodules", scan["submodule_declarations"])
            self.assertIn("run.sh", scan["executables"])
            self.assertIn("archive.zip", scan["archives"])


class GraphOutputTests(unittest.TestCase):
    def test_nested_graphify_out_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            graph_dir = output / "nested" / "graphify-out"
            graph_dir.mkdir(parents=True)
            (graph_dir / "graph.json").write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
            found = discover_graphify_artifacts(output)
            self.assertEqual(graph_dir / "graph.json", found["graph_json"])

    def test_missing_or_invalid_graph_causes_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            with self.assertRaises(GraphifyError):
                discover_graphify_artifacts(output)
            graph = output / "graph.json"
            graph.write_text("not-json", encoding="utf-8")
            with self.assertRaises(GraphifyError):
                validate_graph_json(graph)
            graph.write_text('{"edges":[]}', encoding="utf-8")
            with self.assertRaises(GraphifyError):
                validate_graph_json(graph)

    def test_generated_graph_and_tree_are_self_contained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            graph = {"nodes": [{"id": "a", "name": "A", "file": "a.py"}, {"id": "b", "name": "B", "file": "b.py"}], "edges": [{"source": "a", "target": "b"}]}
            write_safe_graph_preview(graph, root / "graph.html", "owner/repo")
            write_safe_tree_preview(graph, root / "tree.html", "owner/repo")
            for path in (root / "graph.html", root / "tree.html"):
                text = path.read_text(encoding="utf-8").lower().replace("http://www.w3.org/2000/svg", "svg-namespace")
                for forbidden in ("http://", "https://", "//cdn", "fetch(", "xmlhttprequest", "websocket", "eventsource", "<iframe", "<link", "src=\""):
                    self.assertNotIn(forbidden, text)
                self.assertIn("<script>", text)

    def test_generated_graph_preview_has_local_interaction_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "graph.html"
            graph = {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "edges": [{"source": "a", "target": "b"}]}
            write_safe_graph_preview(graph, path, "owner/repo")
            text = path.read_text(encoding="utf-8")
            for contract in (
                'id="zoom-in"', 'id="zoom-out"', 'id="reset"', 'id="details"',
                "function selectNode(index)", "addEventListener('wheel'", "addEventListener('pointerdown'",
                "group.addEventListener('click'", "group.addEventListener('keydown'",
            ):
                self.assertIn(contract, text)
            self.assertNotIn("allow-same-origin", text)


class ArtifactServingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = GraphifyService(brain_root=self.root / "brain", repo_root=self.root / "repo", ingest_script=self.root / "fake.sh")
        self.identity = RepoIdentity("owner", "repository")
        self.clone, self.output = self.service.paths(self.identity)
        graph_dir = self.output / "graphify-out"
        graph_dir.mkdir(parents=True)
        self.clone.mkdir(parents=True)
        provenance = {"owner": "owner", "repository": "repository", "published_output_directory": str(self.output)}
        (self.output / "PROVENANCE.json").write_text(json.dumps(provenance), encoding="utf-8")
        for relative in APPROVED_ARTIFACTS:
            path = self.output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}" if path.suffix == ".json" else "safe", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_only_approved_graphify_system_artifacts_are_served(self):
        for relative in APPROVED_ARTIFACTS:
            path, _ = self.service.artifact("owner", "repository", relative)
            self.assertTrue(path.is_file())
        arbitrary = self.output / "graphify-out" / "cloned-page.html"
        arbitrary.write_text("<script>bad()</script>", encoding="utf-8")
        with self.assertRaises(GraphifyError):
            self.service.artifact("owner", "repository", "graphify-out/cloned-page.html")

    def test_plain_encoded_double_encoded_absolute_null_and_backslash_traversal_rejected(self):
        invalid = ["../PROVENANCE.md", "%2e%2e/PROVENANCE.md", "%252e%252e/PROVENANCE.md", "/etc/passwd", "graphify-out/../PROVENANCE.md", "graphify-out\\graph.json", "graphify-out/graph.json\x00", "graphify-out//graph.json", "./PROVENANCE.md"]
        for relative in invalid:
            with self.subTest(relative=repr(relative)), self.assertRaises(GraphifyError):
                artifact_relative_path(relative)

    def test_symlink_escape_and_non_regular_file_rejected(self):
        graph = self.output / "graphify-out" / "graph.html"
        graph.unlink()
        graph.symlink_to("/etc/passwd")
        with self.assertRaises(GraphifyError):
            self.service.artifact("owner", "repository", "graphify-out/graph.html")
        receipt = self.output / "INGEST_RECEIPT.json"
        receipt.unlink()
        os.mkfifo(receipt)
        with self.assertRaises(GraphifyError):
            self.service.artifact("owner", "repository", "INGEST_RECEIPT.json")

    def test_serving_root_containment_requires_provenance(self):
        (self.output / "PROVENANCE.json").write_text(json.dumps({"owner": "other", "repository": "repository", "published_output_directory": str(self.output)}), encoding="utf-8")
        with self.assertRaises(GraphifyError):
            self.service.artifact("owner", "repository", "PROVENANCE.md")


class FakeGraphifyService(GraphifyService):
    fail_prepare = False

    def _run_ingest_script(self, clone, output, identity):
        graph_dir = output / "graphify-out"
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / "graph.json").write_text('{"nodes":[{"id":"a","name":"A","file":"a.py"}],"edges":[]}', encoding="utf-8")
        (graph_dir / "graph.html").write_text("raw", encoding="utf-8")
        (graph_dir / "GRAPH_TREE.graphify.html").write_text("raw tree", encoding="utf-8")
        return {"argv": ["graphify", "extract", str(clone), "--code-only", "--out", str(output)], "return_code": 0, "graphify_version": "graphify test", "code_only": True}

    def _commit_hash(self, clone):
        return "a" * 40

    def _prepare_output(self, *args, **kwargs):
        if self.fail_prepare:
            raise GraphifyError("forced preparation failure")
        return super()._prepare_output(*args, **kwargs)


class AtomicOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = FakeGraphifyService(brain_root=self.root / "brain", repo_root=self.root / "repo")
        self.identity = RepoIdentity("owner", "repository")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def fake_clone(_source, destination, **_kwargs):
        destination.mkdir(parents=True)
        (destination / "a.py").write_text("A = 1\n", encoding="utf-8")
        return {"argv": ["git", "clone"], "return_code": 0, "shell": False}

    def test_fetch_refuses_existing_and_refetch_is_repository_specific(self):
        with mock.patch("dashboard.backend.graphify_service.run_git_clone", side_effect=self.fake_clone):
            first = self.service.ingest(self.identity.canonical_url)
            self.assertEqual(self.identity.key, first["id"])
            with self.assertRaises(GraphifyError):
                self.service.ingest(self.identity.canonical_url)
            second = self.service.ingest(self.identity.canonical_url, refetch=True)
        clone, output = self.service.paths(self.identity)
        self.assertEqual(self.identity.key, second["id"])
        self.assertTrue(any((clone / ".history").rglob("a.py")))
        self.assertTrue(any((output / ".history").rglob("PROVENANCE.json")))

    def test_failed_refetch_preserves_previous_usable_version_and_cleans_temps(self):
        with mock.patch("dashboard.backend.graphify_service.run_git_clone", side_effect=self.fake_clone):
            self.service.ingest(self.identity.canonical_url)
            clone, output = self.service.paths(self.identity)
            old_provenance = (output / "PROVENANCE.json").read_text(encoding="utf-8")
            self.service.fail_prepare = True
            with self.assertRaises(GraphifyError):
                self.service.ingest(self.identity.canonical_url, refetch=True)
        self.assertTrue(clone.is_dir())
        self.assertEqual(old_provenance, (output / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertFalse(any(path.name.startswith(".tmp-") for path in self.service.clone_root.iterdir()))
        self.assertFalse(any(path.name.startswith(".tmp-") for path in self.service.output_root.iterdir()))

    def test_failed_rebuild_preserves_previous_output(self):
        with mock.patch("dashboard.backend.graphify_service.run_git_clone", side_effect=self.fake_clone):
            self.service.ingest(self.identity.canonical_url)
        _, output = self.service.paths(self.identity)
        old = (output / "PROVENANCE.json").read_text(encoding="utf-8")
        self.service.fail_prepare = True
        with self.assertRaises(GraphifyError):
            self.service.rebuild("owner", "repository")
        self.assertEqual(old, (output / "PROVENANCE.json").read_text(encoding="utf-8"))


class SecurityContractSourceTests(unittest.TestCase):
    def test_ingest_wrapper_uses_controlled_path_and_real_cli_contract(self):
        source = Path("tools/aos-graphify-ingest.sh").read_text(encoding="utf-8")
        self.assertIn('export PATH="/home/liam/.local/bin:/home/liam/.local/npm/bin:$PATH"', source)
        self.assertIn('graphify extract "$clone_path" --code-only --out "$output_path"', source)
        self.assertIn('graphify tree --graph "$graph_json" --output "$tree_output"', source)
        for forbidden in ("eval ", "shell=True", "npm ", "pip ", "docker ", "git push"):
            self.assertNotIn(forbidden, source)

    def test_iframe_sandbox_and_csp_contract(self):
        source = Path("dashboard/frontend/src/views/DashboardV1.jsx").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('sandbox="allow-scripts"'), 2)
        for capability in ("allow-same-origin", "allow-popups", "allow-forms", "allow-downloads", "allow-top-navigation", "allow-top-navigation-by-user-activation"):
            self.assertNotIn(capability, source)
        self.assertIn("default-src 'none'", GRAPH_CSP)
        self.assertIn("connect-src 'none'", GRAPH_CSP)
        self.assertIn("frame-ancestors 'self'", GRAPH_CSP)

    def test_model_boundary_and_queue_item_only_contract(self):
        service = Path("dashboard/backend/graphify_service.py").read_text(encoding="utf-8")
        main = Path("dashboard/backend/main.py").read_text(encoding="utf-8")
        deterministic = service[service.index("    def action("):]
        for model_command in ("hermes", "codex", "claude", "openai", "anthropic"):
            self.assertNotIn(model_command, deterministic.lower())
        endpoint = main[main.index('def graphify_queue_model_work'):main.index('@app.get("/api/graphify/artifacts')]
        self.assertIn("_queue_create_dashboard_item", endpoint)
        self.assertIn('"model_started": False', endpoint)
        self.assertNotIn("subprocess.run", endpoint)

    def test_model_assisted_endpoint_creates_one_queue_item_and_starts_nothing(self):
        from dashboard.backend import test_composio_hermes as backend_harness

        backend = backend_harness.backend
        repository = {
            "id": "owner/repository", "owner": "owner", "repository": "repository",
            "canonical_url": "https://github.com/owner/repository",
            "paths": {"graph_json_path": "/brain/repo_graphs/owner/repository/graphify-out/graph.json", "report_path": "/brain/repo_graphs/owner/repository/graphify-out/GRAPH_REPORT.md"},
        }
        body = backend.GraphifyQueueRequest(owner="owner", repository="repository", requested_work="implementation-context")
        with (
            mock.patch.object(backend.GRAPHIFY_SERVICE, "repository", return_value=repository),
            mock.patch.object(backend, "_queue_create_dashboard_item", return_value={"id": "AOS-TEST-0001"}) as create,
            mock.patch.object(backend, "_queue_detail_item", side_effect=lambda item: item),
            mock.patch.object(backend.subprocess, "run") as process_run,
        ):
            result = backend.graphify_queue_model_work(body)
        self.assertTrue(result["queue_item_only"])
        self.assertFalse(result["model_started"])
        self.assertEqual(1, create.call_count)
        queued = create.call_args.args[0]
        self.assertIn("Repository identity: owner/repository", queued.context)
        self.assertIn("implementation context", queued.definition_of_done.lower())
        self.assertIn("model_invocation_through_open_engine", queued.allowed_actions)
        process_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
