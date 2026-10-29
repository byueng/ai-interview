"""Explicit launcher acceptance: python3 tests/docker/test_launcher.py -v.

Requires a running local Docker engine. Uses temporary config, dummy credentials
and uniquely named test projects. Removes only its own test volumes on exit.
"""
import os
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts/deploy.sh"


class LauncherAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ai-interview launcher ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = self.directory / "model config.env"
        self.environment = {k: v for k, v in os.environ.items() if k not in {
            "API_KEY", "BASE_URL", "MODEL_NAME", "TEMPERATURE", "APP_PORT", "COMPOSE_PROJECT_NAME",
            "AI_INTERVIEW_ANONYMOUS_BUILD", "LANGSMITH_TRACING", "LANGSMITH_API_KEY",
        }}
        self.environment["AI_INTERVIEW_ENV_FILE"] = str(self.config)
        self.project = "ai-interview-launcher-" + uuid4().hex[:10]

    def run_action(self, *args, expected=0):
        result = subprocess.run([str(LAUNCHER), *args], env=self.environment, cwd=self.directory,
                                text=True, capture_output=True, timeout=240)
        self.assertEqual(result.returncode, expected, result.stdout[-3000:] + result.stderr[-3000:])
        return result.stdout + result.stderr

    def write_config(self, *, key="launcher-test-key", port=18089, project=None, base="http://127.0.0.1:9/v1"):
        self.config.write_text(
            f"API_KEY='{key}'\nBASE_URL='{base}'\nMODEL_NAME='launcher-test'\n"
            f"APP_PORT={port}\nCOMPOSE_PROJECT_NAME={project or self.project}\n"
            "LANGSMITH_TRACING=false\nAI_INTERVIEW_ANONYMOUS_BUILD=1\n"
        )

    def compose(self, *args, project=None):
        result = subprocess.run([
            "docker", "compose", "--project-directory", str(ROOT), "--env-file", str(self.config),
            "-f", str(ROOT / "compose.yaml"), "-p", project or self.project, *args,
        ], env=self.environment, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return result.stdout.strip()

    def test_init_is_private_and_preserves_existing_content(self):
        self.run_action("init")
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        original = self.config.read_bytes() + b"\n# preserve this\n"
        self.config.write_bytes(original)
        self.run_action("init")
        self.assertEqual(self.config.read_bytes(), original)

    def test_first_up_names_missing_fields_and_does_not_start(self):
        output = self.run_action("up", expected=2)
        for name in ("API_KEY", "BASE_URL", "MODEL_NAME"):
            self.assertIn(name, output)
        self.assertNotIn("服务已就绪", output)

    def test_dotenv_is_not_executed_and_secret_is_not_printed(self):
        marker = self.directory / "should-not-exist"
        secret = f"literal-$key-$(touch {marker})"
        self.write_config(key=secret)
        output = self.run_action("doctor")
        self.assertNotIn(secret, output)
        self.assertFalse(marker.exists())

    def test_invalid_port_and_url_fail_before_start(self):
        for port in (0, -1, 65536, "abc"):
            self.write_config(port=port)
            self.assertIn("APP_PORT", self.run_action("up", expected=2))
        self.write_config(base="not-a-url")
        self.assertIn("BASE_URL", self.run_action("up", expected=2))

    def test_unknown_and_extra_arguments_fail(self):
        self.run_action("unknown", expected=2)
        self.run_action("up", "--volumes", expected=2)

    def test_start_repeat_stop_failure_and_data_retention(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.write_config(port=port)
        self.addCleanup(lambda: self.compose("down", "--volumes", project=self.project))
        first = self.run_action("up")
        self.assertIn(f"http://127.0.0.1:{port}", first)
        self.assertEqual(self.run_action("url").strip(), f"http://127.0.0.1:{port}")
        container = self.compose("ps", "-q", "backend")
        self.assertTrue(container)
        self.compose("exec", "-T", "backend", "python", "-c",
                     "from pathlib import Path; Path('/app/data/launcher-marker').write_text('keep')")
        self.run_action("up")
        self.assertEqual(self.compose("ps", "-q", "backend"), container)

        conflict = self.project + "-conflict"
        self.addCleanup(lambda: self.compose("down", "--volumes", project=conflict))
        self.write_config(port=port, project=conflict)
        output = self.run_action("up", expected=1)
        self.assertNotIn("服务已就绪", output)
        self.assertIn("部署未完成", output)
        self.compose("down", "--volumes", project=conflict)

        self.write_config(port=port)
        self.run_action("stop")
        self.assertEqual(self.compose("ps", "--status", "running", "-q"), "")
        # Management still works if model credentials are removed.
        self.write_config(port=port, key="")
        self.run_action("status")
        self.run_action("down")
        self.assertEqual(self.compose("ps", "--all", "-q"), "")
        marker = self.compose("run", "--rm", "--no-deps", "backend", "python", "-c",
                              "from pathlib import Path; print(Path('/app/data/launcher-marker').read_text())")
        self.assertEqual(marker, "keep")


if __name__ == "__main__":
    unittest.main()
