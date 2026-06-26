import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LAUNCHERS = (
    SCRIPTS / "start_north_shore_bot.sh",
    SCRIPTS / "Start-North-Shore-Sales-Coach-Bot.ps1",
    SCRIPTS / "Start-North-Shore-Sales-Coach-Bot-Hidden.vbs",
    SCRIPTS / "Install-North-Shore-Startup.ps1",
    SCRIPTS / "Remove-North-Shore-Startup.ps1",
    SCRIPTS / "Get-North-Shore-Bot-Status.ps1",
    SCRIPTS / "setup_local_secret.ps1",
)


class LocalLauncherTests(unittest.TestCase):
    def test_launcher_files_exist(self):
        for path in LAUNCHERS:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())

    def test_local_runtime_and_logs_are_gitignored(self):
        ignore_lines = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn(".runtime/", ignore_lines)
        self.assertIn("logs/", ignore_lines)

    def test_launchers_are_isolated_and_contain_no_token_value(self):
        combined = "\n".join(path.read_text(encoding="utf-8") for path in LAUNCHERS)
        self.assertIn("src.north_shore_bot_runner", combined)
        self.assertIn("NORTH_SHORE_TELEGRAM_BOT_TOKEN", combined)
        self.assertIn("NORTH_SHORE_SHEETS_WEBAPP_URL", combined)
        self.assertIn("NORTH_SHORE_SHEETS_WEBAPP_SECRET", combined)
        bridge_name = "telegram_" + "bridge"
        self.assertNotIn("connectors/" + bridge_name, combined)
        self.assertNotIn(bridge_name, combined)
        self.assertNotIn("composio", combined.lower())
        self.assertNotIn("hermes", combined.lower())
        self.assertNotIn("/exec", combined)
        self.assertIsNone(re.search(r"\b[0-9]{6,}:[A-Za-z0-9_-]{20,}\b", combined))

    def test_windows_startup_launcher_targets_wsl_package_runner_and_logs(self):
        launcher = (SCRIPTS / "Start-North-Shore-Sales-Coach-Bot.ps1").read_text(encoding="utf-8")
        self.assertIn("$Distro = 'AgenticOSClean'", launcher)
        self.assertIn("wsl.exe -d $Distro --user $LinuxUser", launcher)
        self.assertIn("wslpath -a $PackageDirectoryWindows", launcher)
        self.assertIn("cd $QuotedPackageDirectory", launcher)
        self.assertIn("exec scripts/start_north_shore_bot.sh", launcher)
        self.assertIn("logs/north_shore_bot.log", launcher)
        self.assertIn(">> $QuotedLogFile 2>&1", launcher)

    def test_startup_install_remove_are_separate_named_shortcut(self):
        install = (SCRIPTS / "Install-North-Shore-Startup.ps1").read_text(encoding="utf-8")
        remove = (SCRIPTS / "Remove-North-Shore-Startup.ps1").read_text(encoding="utf-8")
        for content in (install, remove):
            self.assertIn("North Shore Sales Coach Bot.lnk", content)
            self.assertIn("[Environment]::GetFolderPath('Startup')", content)
        self.assertIn("Start-North-Shore-Sales-Coach-Bot-Hidden.vbs", install)
        self.assertIn("wscript.exe", install)
        self.assertIn("//B //Nologo", install)
        self.assertNotIn("Start-North-Shore-Sales-Coach-Bot.ps1", install)
        self.assertNotIn("powershell.exe", install)

    def test_hidden_startup_launcher_runs_visible_launcher_without_window(self):
        hidden = (SCRIPTS / "Start-North-Shore-Sales-Coach-Bot-Hidden.vbs").read_text(encoding="utf-8")
        self.assertIn("Start-North-Shore-Sales-Coach-Bot.ps1", hidden)
        self.assertIn("powershell.exe -NoProfile -ExecutionPolicy Bypass -File", hidden)
        self.assertIn("shell.Run command, 0, False", hidden)

    def test_status_script_reports_runner_count_without_process_details(self):
        status = (SCRIPTS / "Get-North-Shore-Bot-Status.ps1").read_text(encoding="utf-8")
        self.assertIn("$Distro = 'AgenticOSClean'", status)
        self.assertIn("src\\.north_shore_bot_runner", status)
        self.assertIn("pgrep -u", status)
        self.assertIn("wc -l", status)
        self.assertIn("Expected exactly one North Shore runner", status)
        self.assertNotIn("pgrep -af", status)

    def test_bash_launcher_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPTS / "start_north_shore_bot.sh")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bash_launcher_loads_secret_file_and_prints_only_safe_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            secret_file = temp / "north_shore_bot.env"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            secret_file.write_text(
                "\n".join(
                    [
                        "NORTH_SHORE_TELEGRAM_BOT_TOKEN='123456:fake-token-value'",
                        "NORTH_SHORE_SHEETS_PROVIDER=apps_script_webapp",
                        "NORTH_SHORE_SHEETS_WEBAPP_URL='https://example.invalid/apps-script-webapp'",
                        "NORTH_SHORE_SHEETS_WEBAPP_SECRET='fake-shared-secret'",
                        "NORTH_SHORE_SHEETS_EXECUTION_ENABLED=true",
                        "NORTH_SHORE_SHEETS_WRITES_ENABLED=true",
                        "NORTH_SHORE_SHEETS_READS_ENABLED=false",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (fake_bin / "pgrep").write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            (fake_bin / "python3").write_text(
                "#!/usr/bin/env bash\n"
                "printf 'python saw provider=%s url_length=%s secret_length=%s\\n' "
                "\"$NORTH_SHORE_SHEETS_PROVIDER\" "
                "\"${#NORTH_SHORE_SHEETS_WEBAPP_URL}\" "
                "\"${#NORTH_SHORE_SHEETS_WEBAPP_SECRET}\"\n",
                encoding="utf-8",
            )
            (fake_bin / "pgrep").chmod(0o755)
            (fake_bin / "python3").chmod(0o755)
            result = subprocess.run(
                ["bash", str(SCRIPTS / "start_north_shore_bot.sh")],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                env={
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "NORTH_SHORE_SECRET_FILE": str(secret_file),
                },
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("token_length=23", result.stdout)
        self.assertIn("sheets_provider=apps_script_webapp", result.stdout)
        self.assertIn("sheets_url_length=42", result.stdout)
        self.assertIn("sheets_secret_length=18", result.stdout)
        self.assertIn("sheets_execution_enabled=true", result.stdout)
        self.assertIn("python saw provider=apps_script_webapp url_length=42 secret_length=18", result.stdout)
        self.assertNotIn("123456:fake-token-value", result.stdout + result.stderr)
        self.assertNotIn("https://example.invalid/apps-script-webapp", result.stdout + result.stderr)
        self.assertNotIn("fake-shared-secret", result.stdout + result.stderr)

    def test_bash_launcher_refuses_duplicate_runner_when_detectable(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            (fake_bin / "pgrep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fake_bin / "pgrep").chmod(0o755)
            result = subprocess.run(
                ["bash", str(SCRIPTS / "start_north_shore_bot.sh")],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("already active", result.stderr)
        self.assertIn("refusing to start a second runner", result.stderr)


if __name__ == "__main__":
    unittest.main()
