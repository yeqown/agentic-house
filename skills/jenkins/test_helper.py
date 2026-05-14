import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parent / "scripts" / "helper.py"
SPEC = importlib.util.spec_from_file_location("jenkins_helper", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TriggerCommandTest(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int, dict]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = MODULE.main(argv)
        return exit_code, json.loads(stdout.getvalue())

    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_resolve_metadata")
    def test_trigger_command_uses_preflight_metadata_without_resolving_metadata_again(
        self,
        resolve_metadata: mock.Mock,
        resolve_runtime_config: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "jenkins-cli.jar").write_text("jar", encoding="utf-8")
            resolve_runtime_config.return_value = {
                "ok": True,
                "host": "https://jenkins.example.com/",
                "auth": "bot:token",
                "runtimeRoot": str(root),
            }

            exit_code, payload = self.run_main([
                "trigger-command",
                "--job-path",
                "team/project",
                "--available-param",
                "GitBranch",
                "--available-param",
                "DeployMicroServices",
                "--param",
                "GitBranch=feature/test",
                "--param",
                "DeployMicroServices=api",
            ])

        self.assertEqual(exit_code, 0)
        resolve_metadata.assert_not_called()
        self.assertEqual(payload["jobPath"], "team/project")
        self.assertEqual(payload["parameters"], {
            "GitBranch": "feature/test",
            "DeployMicroServices": "api",
        })
        self.assertEqual(payload["argv"][-5:], [
            "team/project",
            "-p",
            "GitBranch=feature/test",
            "-p",
            "DeployMicroServices=api",
        ])

    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_resolve_metadata")
    def test_trigger_command_rejects_parameters_not_in_preflight_metadata(
        self,
        resolve_metadata: mock.Mock,
        resolve_runtime_config: mock.Mock,
    ) -> None:
        resolve_runtime_config.return_value = {
            "ok": True,
            "host": "https://jenkins.example.com/",
            "auth": "bot:token",
            "runtimeRoot": "/tmp/unused",
        }

        exit_code, payload = self.run_main([
            "trigger-command",
            "--job-path",
            "team/project",
            "--available-param",
            "GitBranch",
            "--param",
            "Unknown=value",
        ])

        self.assertEqual(exit_code, 1)
        resolve_metadata.assert_not_called()
        resolve_runtime_config.assert_not_called()
        self.assertEqual(payload["error"], "unknown Jenkins parameter")
        self.assertEqual(payload["parameter"], "Unknown")
        self.assertEqual(payload["availableParameters"], ["GitBranch"])
