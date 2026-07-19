import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Revisit: when desktop cleanup or external runner supervision changes. · Last touched: 2026-07-19.


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tools" / "aos-linux-runtime.sh"
SLEEPER = "import time; time.sleep(60)"


class DashboardCleanupTests(unittest.TestCase):
    def setUp(self):
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def spawn(self, cwd, *display_args):
        process = subprocess.Popen(
            [sys.executable, "-c", SLEEPER, *map(str, display_args)],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes.append(process)
        return process

    def assert_survives(self, process):
        self.assertIsNone(process.poll(), f"PID {process.pid} was killed unexpectedly")

    def test_cleanup_kills_only_precise_live_root_dashboard_processes_and_logs_each(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            frontend = root / "dashboard" / "frontend"
            frontend.mkdir(parents=True)
            (root / "tools").mkdir()

            runner = self.spawn(root, root / "tools" / "aos-orchestration-runner.py")
            relative_runner = self.spawn(
                root,
                "tools/aos-orchestration-runner.py", "--root", root,
                "--skip-telegram-escalation", "--watch", "--interval", "5",
            )
            backend = self.spawn(root / "dashboard", "-m", "uvicorn", "backend.main:app", "--port", "8010")
            vite = self.spawn(
                frontend,
                root / "dashboard" / "frontend" / "node_modules" / ".bin" / ".." / "vite" / "bin" / "vite.js",
                "--host", "127.0.0.1", "--port", "3010",
            )
            esbuild = self.spawn(
                frontend,
                root / "dashboard" / "frontend" / "node_modules" / "@esbuild" / "linux-x64" / "bin" / "esbuild",
                "--service=0.25.12", "--ping",
            )

            plain_sleep = subprocess.Popen(["sleep", "60"], cwd=root)
            self.processes.append(plain_sleep)
            wrong_port = self.spawn(root / "dashboard", "-m", "uvicorn", "backend.main:app", "--port", "8999")
            north_shore = self.spawn(
                root,
                "north_shore_bot_runner",
                "-m", "uvicorn", "backend.main:app", "--port", "8010",
            )
            hermes = self.spawn(
                frontend,
                "hermes",
                root / "dashboard" / "frontend" / "node_modules" / "vite" / "bin" / "vite.js",
                "--port", "3010",
            )

            with tempfile.TemporaryDirectory(dir="/tmp") as outside_tmp:
                outside = self.spawn(
                    Path(outside_tmp), "-m", "uvicorn", "backend.main:app", "--port", "8010"
                )
                time.sleep(0.1)
                result = subprocess.run(
                    ["bash", str(RUNTIME), "desktop-cleanup"],
                    cwd=ROOT,
                    env={**os.environ, "AOS_ROOT": str(root)},
                    text=True,
                    capture_output=True,
                    timeout=10,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                killed = [runner, relative_runner, backend, vite, esbuild]
                for process in killed:
                    process.wait(timeout=2)
                    self.assertIn(f"cleanup killed pid={process.pid} ", result.stdout)
                self.assertEqual(5, result.stdout.count("cleanup killed pid="), result.stdout)
                self.assertIn("process=orchestration runner", result.stdout)
                self.assertIn("process=dashboard backend (uvicorn :8010)", result.stdout)
                self.assertIn("process=dashboard frontend (vite :3010)", result.stdout)
                self.assertIn("process=dashboard frontend (esbuild for vite :3010)", result.stdout)

                for survivor in (plain_sleep, wrong_port, north_shore, hermes, outside):
                    self.assert_survives(survivor)

    def test_status_recognizes_one_externally_supervised_relative_runner(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            runner = self.spawn(
                root,
                "tools/aos-orchestration-runner.py", "--root", root,
                "--skip-telegram-escalation", "--watch", "--interval", "5",
            )
            time.sleep(0.1)
            result = subprocess.run(
                ["bash", str(RUNTIME), "status"],
                cwd=ROOT,
                env={**os.environ, "AOS_ROOT": str(root)},
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn(
                f"runner=running pid={runner.pid} root={root} supervisor=external",
                result.stdout,
            )
            self.assertNotIn("runner=stopped", result.stdout)


if __name__ == "__main__":
    unittest.main()
