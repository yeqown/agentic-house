import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "plugins/jenkins-skill/bin/jenkins-skill"
REMOTE_URL = "ssh://git@git.easycodesource.com:2222/nova/game-portal/lobby-mono.git"
JOB_PATH = "nova/game-portal/lobby-mono"
PARAMETER_NAMES = [
    "GitBranch",
    "OperatingEnvs",
    "OperationType",
    "DeployMicroServices",
    "Namespace",
    "AdditionalOps",
]


def run_cli(args, repo_dir, runtime_dir):
    env = os.environ.copy()
    env["JENKINS_SKILL_HOME"] = str(runtime_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def init_repo(repo_dir: Path, remote_url: str):
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=repo_dir, check=True, capture_output=True)


def write_config(runtime_dir: Path):
    payload = {
        "host": "https://jenkins.offline-ops.net/",
        "auth": "user:token",
        "parameters": [
            {"name": "GitBranch", "required": True, "default": "git.branch"},
            {
                "name": "OperatingEnvs",
                "required": True,
                "availableValues": [
                    {"value": "local01", "description": "香港 int2 测试环境 local01"},
                    {"value": "global", "description": "全球环境"},
                ],
            },
            {
                "name": "OperationType",
                "required": True,
                "default": "FullDeploy",
                "availableValues": [{"value": "FullDeploy", "description": "full"}],
            },
            {"name": "DeployMicroServices", "required": True, "default": ""},
            {"name": "Namespace", "required": False},
            {"name": "AdditionalOps", "required": True, "default": ""},
        ],
    }
    (runtime_dir / "index.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (runtime_dir / "jenkins-cli.jar").write_text("jar", encoding="utf-8")


class JenkinsSkillTest(unittest.TestCase):
    def make_case(self, remote_url: str):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        repo_dir = base / "repo"
        runtime_dir = base / "runtime"
        repo_dir.mkdir()
        runtime_dir.mkdir()
        write_config(runtime_dir)
        init_repo(repo_dir, remote_url)
        return repo_dir, runtime_dir

    def test_metadata_outputs_context_runtime_and_parameter_definitions(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)

        result = run_cli(["metadata"], repo_dir, runtime_dir)

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["branch"], "feature/test")
        self.assertEqual(payload["jobPath"], JOB_PATH)
        self.assertEqual(payload["host"], "https://jenkins.offline-ops.net/")
        self.assertEqual(payload["runtimeRoot"], str(runtime_dir))
        self.assertEqual(
            [parameter["name"] for parameter in payload["parameters"]],
            PARAMETER_NAMES,
        )
        self.assertEqual(
            payload["parameters"][1]["availableValues"],
            [
                {"value": "local01", "description": "香港 int2 测试环境 local01"},
                {"value": "global", "description": "全球环境"},
            ],
        )

    def test_metadata_normalizes_non_string_parameter_name(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)
        payload = {
            "host": "https://jenkins.offline-ops.net/",
            "auth": "user:token",
            "parameters": [{"name": 123, "required": True}],
        }
        (runtime_dir / "index.json").write_text(json.dumps(payload), encoding="utf-8")

        result = run_cli(["metadata"], repo_dir, runtime_dir)

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["parameters"][0]["name"], "123")

    def test_metadata_returns_structured_error_for_malformed_index_json(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)
        (runtime_dir / "index.json").write_text("{invalid json", encoding="utf-8")

        result = run_cli(["metadata"], repo_dir, runtime_dir)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("index.json cannot be read", payload["error"])

    def test_runtime_returns_structured_error_for_malformed_index_json(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)
        (runtime_dir / "index.json").write_text("{invalid json", encoding="utf-8")

        result = run_cli(["runtime"], repo_dir, runtime_dir)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("index.json cannot be read", payload["error"])

    def test_params_subcommand_is_removed(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)

        result = run_cli(["params", "--env", "local01"], repo_dir, runtime_dir)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("params", result.stderr)

    def test_trigger_command_builds_jenkins_cli_argv_from_explicit_parameters(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)

        result = run_cli(
            [
                "trigger-command",
                "--param",
                "GitBranch=feature/test",
                "--param",
                "OperatingEnvs=香港 int2 测试环境 local01",
                "--param",
                "OperationType=FullDeploy",
                "--param",
                "DeployMicroServices=game-openapi,game-api",
                "--param",
                "AdditionalOps=",
            ],
            repo_dir,
            runtime_dir,
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["jobPath"], JOB_PATH)
        self.assertEqual(
            payload["parameters"],
            {
                "GitBranch": "feature/test",
                "OperatingEnvs": "香港 int2 测试环境 local01",
                "OperationType": "FullDeploy",
                "DeployMicroServices": "game-openapi,game-api",
                "AdditionalOps": "",
            },
        )
        self.assertEqual(
            payload["argv"],
            [
                "java",
                "-jar",
                str(runtime_dir / "jenkins-cli.jar"),
                "-s",
                "https://jenkins.offline-ops.net/",
                "-auth",
                "user:token",
                "build",
                JOB_PATH,
                "-p",
                "GitBranch=feature/test",
                "-p",
                "OperatingEnvs=香港 int2 测试环境 local01",
                "-p",
                "OperationType=FullDeploy",
                "-p",
                "DeployMicroServices=game-openapi,game-api",
                "-p",
                "AdditionalOps=",
            ],
        )

    def test_trigger_command_rejects_unknown_parameter_names(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)

        result = run_cli(
            ["trigger-command", "--param", "UnknownParam=value"],
            repo_dir,
            runtime_dir,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload,
            {
                "ok": False,
                "error": "unknown Jenkins parameter",
                "parameter": "UnknownParam",
                "availableParameters": PARAMETER_NAMES,
            },
        )

    def test_trigger_command_fails_when_jenkins_cli_jar_is_missing(self):
        repo_dir, runtime_dir = self.make_case(REMOTE_URL)
        (runtime_dir / "jenkins-cli.jar").unlink()

        result = run_cli(
            ["trigger-command", "--param", "GitBranch=feature/test"],
            repo_dir,
            runtime_dir,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload,
            {
                "ok": False,
                "error": "jenkins-cli.jar is missing",
                "path": str(runtime_dir / "jenkins-cli.jar"),
            },
        )


if __name__ == "__main__":
    unittest.main()
