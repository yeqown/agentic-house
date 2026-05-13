import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("bin") / "jenkins-skill"
LOADER = importlib.machinery.SourceFileLoader("jenkins_skill", str(MODULE_PATH))
SPEC = importlib.util.spec_from_loader("jenkins_skill", LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


class JenkinsSkillCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index.json").write_text(
            json.dumps(
                {
                    "host": "https://jenkins.example.com/",
                    "auth": "bot:token",
                    "parameters": [],
                }
            ),
            encoding="utf-8",
        )
        self.old_home = os.environ.get("JENKINS_SKILL_HOME")
        os.environ["JENKINS_SKILL_HOME"] = str(self.root)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("JENKINS_SKILL_HOME", None)
        else:
            os.environ["JENKINS_SKILL_HOME"] = self.old_home
        self.temp_dir.cleanup()

    def run_main(self, argv: list[str]) -> tuple[int, dict]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = MODULE.main(argv)
        return exit_code, json.loads(stdout.getvalue())

    @mock.patch.object(MODULE, "_resolve_context")
    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_jenkins_get")
    def test_job_parameters_returns_normalized_parameter_definitions(
        self,
        jenkins_get: mock.Mock,
        resolve_runtime: mock.Mock,
        resolve_context: mock.Mock,
    ) -> None:
        resolve_context.return_value = {
            "ok": True,
            "jobPath": "team/project",
            "branch": "feature/test",
            "remote": "git@git.example.com:team/project.git",
        }
        resolve_runtime.return_value = {
            "ok": True,
            "host": "https://jenkins.example.com/",
            "auth": "bot:token",
            "runtimeRoot": str(self.root),
        }
        jenkins_get.return_value = {
            "property": [
                {
                    "parameterDefinitions": [
                        {
                            "name": "Branch",
                            "type": "StringParameterDefinition",
                            "description": "branch to build",
                            "defaultParameterValue": {"value": "main"},
                        },
                        {
                            "name": "Targets",
                            "type": "ChoiceParameterDefinition",
                            "description": "services to deploy",
                            "choices": ["api", "worker"],
                            "defaultParameterValue": {"value": "api"},
                        },
                        {
                            "name": "DryRun",
                            "type": "BooleanParameterDefinition",
                            "description": "skip real deploy",
                            "defaultParameterValue": {"value": True},
                        },
                    ]
                }
            ]
        }

        exit_code, payload = self.run_main(["job-parameters"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["jobPath"], "team/project")
        self.assertEqual(len(payload["parameters"]), 3)
        self.assertEqual(payload["parameters"][0]["type"], "string")
        self.assertEqual(payload["parameters"][0]["default"], "main")
        self.assertEqual(payload["parameters"][1]["type"], "choice")
        self.assertEqual(payload["parameters"][1]["availableValues"], ["api", "worker"])
        self.assertEqual(payload["parameters"][2]["type"], "boolean")
        self.assertEqual(payload["parameters"][2]["default"], True)

    @mock.patch.object(MODULE, "_resolve_context")
    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_jenkins_get")
    def test_job_parameters_returns_empty_list_when_job_has_no_parameters(
        self,
        jenkins_get: mock.Mock,
        resolve_runtime: mock.Mock,
        resolve_context: mock.Mock,
    ) -> None:
        resolve_context.return_value = {
            "ok": True,
            "jobPath": "team/project",
            "branch": "main",
            "remote": "git@git.example.com:team/project.git",
        }
        resolve_runtime.return_value = {
            "ok": True,
            "host": "https://jenkins.example.com/",
            "auth": "bot:token",
            "runtimeRoot": str(self.root),
        }
        jenkins_get.return_value = {"property": []}

        exit_code, payload = self.run_main(["job-parameters"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["parameters"], [])

    @mock.patch.object(MODULE, "_resolve_context")
    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_jenkins_get")
    def test_job_parameters_preserves_unknown_parameter_type(
        self,
        jenkins_get: mock.Mock,
        resolve_runtime: mock.Mock,
        resolve_context: mock.Mock,
    ) -> None:
        resolve_context.return_value = {
            "ok": True,
            "jobPath": "team/project",
            "branch": "main",
            "remote": "git@git.example.com:team/project.git",
        }
        resolve_runtime.return_value = {
            "ok": True,
            "host": "https://jenkins.example.com/",
            "auth": "bot:token",
            "runtimeRoot": str(self.root),
        }
        jenkins_get.return_value = {
            "property": [
                {
                    "parameterDefinitions": [
                        {
                            "name": "Custom",
                            "type": "ExtendedChoiceParameterDefinition",
                            "description": "custom plugin parameter",
                        }
                    ]
                }
            ]
        }

        exit_code, payload = self.run_main(["job-parameters"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["parameters"][0]["type"], "ExtendedChoiceParameterDefinition")
        self.assertEqual(payload["parameters"][0]["availableValues"], [])

    @mock.patch.object(MODULE, "_resolve_context")
    @mock.patch.object(MODULE, "_resolve_runtime_config")
    @mock.patch.object(MODULE, "_jenkins_get")
    def test_job_parameters_returns_error_when_jenkins_lookup_fails(
        self,
        jenkins_get: mock.Mock,
        resolve_runtime: mock.Mock,
        resolve_context: mock.Mock,
    ) -> None:
        resolve_context.return_value = {
            "ok": True,
            "jobPath": "team/project",
            "branch": "main",
            "remote": "git@git.example.com:team/project.git",
        }
        resolve_runtime.return_value = {
            "ok": True,
            "host": "https://jenkins.example.com/",
            "auth": "bot:token",
            "runtimeRoot": str(self.root),
        }
        jenkins_get.side_effect = RuntimeError("Jenkins auth failed — check index.json auth credentials")

        exit_code, payload = self.run_main(["job-parameters"])

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "Jenkins auth failed — check index.json auth credentials")


if __name__ == "__main__":
    unittest.main()
