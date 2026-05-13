# Jenkins Skill Build Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded Jenkins build parameter assembly with a metadata-driven flow where the LLM reads parameter definitions, asks for missing inputs, confirms the final Jenkins CLI command, then triggers the build.

**Architecture:** The helper CLI owns deterministic repository/runtime/Jenkins metadata and safe Jenkins API helpers. The skill instructions own semantic mapping from user intent to Jenkins parameters using the helper's metadata output. The old `params --env ...` pre-assembly flow is removed so business parameter names are not baked into code or workflow docs.

**Tech Stack:** Python 3 standard library, `unittest`, Jenkins CLI jar, Claude Code skill markdown.

---

## File Structure

- Modify `plugins/jenkins-skill/bin/jenkins-skill`
  - Keep existing `context`, `runtime`, `last-build`, and `console-log` commands.
  - Add `metadata` command that outputs complete Jenkins parameter definitions plus derived context/runtime metadata.
  - Remove `params` subcommand and all parameter pre-assembly logic.
  - Add `trigger-command` command that validates user-supplied `name=value` pairs against metadata and emits the exact Jenkins CLI command argv; it must not infer business values.
- Modify `plugins/jenkins-skill/tests/test_jenkins_skill.py`
  - Replace tests for `params --env ...` with tests for metadata output, params command removal, and trigger-command validation/argv generation.
- Modify `plugins/jenkins-skill/skills/jenkins-skill/SKILL.md`
  - Reframe build workflow: user intent → metadata → LLM parameter mapping → ask user for missing/ambiguous values → confirmation → Jenkins CLI execution.
  - Remove hardcoded `OperatingEnvs`, `DeployMicroServices`, `OperationType`, `AdditionalOps`, `Namespace` rules from workflow.
- Modify `plugins/jenkins-skill/skills/jenkins-skill/reference.md`
  - Document generic parameter schema and helper commands.
  - Move current sample parameter names into examples only, not rules.
- Modify `plugins/jenkins-skill/README.md`
  - Document operator/developer flow with `metadata` and `trigger-command`.
  - Remove `params --env ...` usage.

---

### Task 1: Add failing tests for metadata-driven helper flow

**Files:**
- Modify: `plugins/jenkins-skill/tests/test_jenkins_skill.py`

- [ ] **Step 1: Replace old params behavior tests with metadata/trigger tests**

In `plugins/jenkins-skill/tests/test_jenkins_skill.py`, replace `test_params_accepts_apps_alias_for_services` and `test_params_reports_available_env_choices_when_env_invalid` with:

```python
    def test_metadata_outputs_context_runtime_and_parameter_definitions(self):
        repo_dir, runtime_dir = self.make_case(
            "ssh://git@git.easycodesource.com:2222/nova/game-portal/lobby-mono.git"
        )

        result = run_cli(["metadata"], repo_dir, runtime_dir)

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["branch"], "feature/test")
        self.assertEqual(payload["jobPath"], "nova/game-portal/lobby-mono")
        self.assertEqual(payload["host"], "https://jenkins.offline-ops.net/")
        self.assertEqual(payload["runtimeRoot"], str(runtime_dir))
        self.assertEqual(
            [parameter["name"] for parameter in payload["parameters"]],
            [
                "GitBranch",
                "OperatingEnvs",
                "OperationType",
                "DeployMicroServices",
                "Namespace",
                "AdditionalOps",
            ],
        )
        self.assertEqual(
            payload["parameters"][1]["availableValues"],
            [
                {"value": "local01", "description": "香港 int2 测试环境 local01"},
                {"value": "global", "description": "全球环境"},
            ],
        )

    def test_params_subcommand_is_removed(self):
        repo_dir, runtime_dir = self.make_case(
            "ssh://git@git.easycodesource.com:2222/nova/game-portal/lobby-mono.git"
        )

        result = run_cli(["params", "--env", "local01"], repo_dir, runtime_dir)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
```

- [ ] **Step 2: Add trigger-command tests**

Append these tests inside `JenkinsSkillTest`:

```python
    def test_trigger_command_builds_jenkins_cli_argv_from_explicit_parameters(self):
        repo_dir, runtime_dir = self.make_case(
            "ssh://git@git.easycodesource.com:2222/nova/game-portal/lobby-mono.git"
        )

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
        self.assertEqual(payload["jobPath"], "nova/game-portal/lobby-mono")
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
                "nova/game-portal/lobby-mono",
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
        repo_dir, runtime_dir = self.make_case(
            "ssh://git@git.easycodesource.com:2222/nova/game-portal/lobby-mono.git"
        )

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
                "availableParameters": [
                    "GitBranch",
                    "OperatingEnvs",
                    "OperationType",
                    "DeployMicroServices",
                    "Namespace",
                    "AdditionalOps",
                ],
            },
        )
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
python3 -m unittest "plugins/jenkins-skill/tests/test_jenkins_skill.py"
```

Expected:

```text
FAILED
```

Expected failure reasons:
- `metadata` is not a valid subcommand.
- `trigger-command` is not a valid subcommand.
- `params` still exists, so removal test fails until implementation.

---

### Task 2: Implement metadata and trigger-command helper commands

**Files:**
- Modify: `plugins/jenkins-skill/bin/jenkins-skill`
- Test: `plugins/jenkins-skill/tests/test_jenkins_skill.py`

- [ ] **Step 1: Add reusable metadata resolver**

In `plugins/jenkins-skill/bin/jenkins-skill`, after `_resolve_runtime_config`, add:

```python
def _resolve_metadata() -> dict:
    ctx = _resolve_context()
    if not ctx.get("ok"):
        return ctx

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return rt

    config = load_config(Path(rt["runtimeRoot"]))
    parameters = config.get("parameters", [])
    if not isinstance(parameters, list):
        return {"ok": False, "error": "index.json parameters must be a list", "runtimeRoot": rt["runtimeRoot"]}

    normalized_parameters = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        name = str(parameter.get("name", "")).strip()
        if not name:
            continue
        normalized_parameters.append(parameter)

    return {
        "ok": True,
        "remote": ctx["remote"],
        "branch": ctx["branch"],
        "host": rt["host"],
        "runtimeRoot": rt["runtimeRoot"],
        "jobPath": ctx["jobPath"],
        "parameters": normalized_parameters,
    }
```

- [ ] **Step 2: Add `metadata` command**

After `command_runtime`, add:

```python
def command_metadata(_: argparse.Namespace) -> int:
    payload = _resolve_metadata()
    return emit(payload, 0 if payload.get("ok") else 1)
```

- [ ] **Step 3: Add parameter parsing helper**

After `command_metadata`, add:

```python
def _parse_param_values(values: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"invalid parameter assignment: {value}")
        name, param_value = value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"invalid parameter assignment: {value}")
        params[name] = param_value
    return params
```

- [ ] **Step 4: Add `trigger-command` command**

After `_parse_param_values`, add:

```python
def command_trigger_command(args: argparse.Namespace) -> int:
    metadata = _resolve_metadata()
    if not metadata.get("ok"):
        return emit(metadata, 1)

    try:
        params = _parse_param_values(args.param or [])
    except ValueError as e:
        return emit({"ok": False, "error": str(e)}, 1)

    parameter_names = [parameter["name"] for parameter in metadata["parameters"]]
    allowed = set(parameter_names)
    for name in params:
        if name not in allowed:
            return emit(
                {
                    "ok": False,
                    "error": "unknown Jenkins parameter",
                    "parameter": name,
                    "availableParameters": parameter_names,
                },
                1,
            )

    root = Path(metadata["runtimeRoot"])
    config = load_config(root)
    auth = str(config.get("auth", "")).strip()
    argv = [
        "java",
        "-jar",
        str(root / "jenkins-cli.jar"),
        "-s",
        metadata["host"],
        "-auth",
        auth,
        "build",
        metadata["jobPath"],
    ]
    for name, value in params.items():
        argv.extend(["-p", f"{name}={value}"])

    return emit({"ok": True, "jobPath": metadata["jobPath"], "parameters": params, "argv": argv})
```

- [ ] **Step 5: Replace parser subcommands**

In `build_parser`, remove this block:

```python
    params_parser = subparsers.add_parser("params")
    params_parser.add_argument("--env", required=True)
    params_parser.add_argument("--operation-type")
    params_parser.add_argument("--services")
    params_parser.add_argument("--apps", dest="services")
    params_parser.add_argument("--namespace")
    params_parser.set_defaults(handler=command_params)
```

Add this block after runtime parser:

```python
    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.set_defaults(handler=command_metadata)

    trigger_parser = subparsers.add_parser("trigger-command")
    trigger_parser.add_argument("--param", action="append", default=[])
    trigger_parser.set_defaults(handler=command_trigger_command)
```

- [ ] **Step 6: Remove old `command_params` function**

Delete `command_params` entirely from `plugins/jenkins-skill/bin/jenkins-skill`. Keep `load_parameters` only if still used; after deleting `command_params`, remove `load_parameters` too if no references remain.

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
python3 -m unittest "plugins/jenkins-skill/tests/test_jenkins_skill.py"
```

Expected:

```text
OK
```

---

### Task 3: Update skill workflow docs to make LLM own semantic parameter assembly

**Files:**
- Modify: `plugins/jenkins-skill/skills/jenkins-skill/SKILL.md`

- [ ] **Step 1: Update overview**

Replace the overview paragraph with:

```markdown
Natural-language Jenkins workflow for repos on `git.example.com`. Use helper CLI output for deterministic git/runtime/Jenkins metadata. The LLM must map user build intent to Jenkins parameters from the parameter definitions returned by `bin/jenkins-skill metadata`; helper code must not hardcode business parameter names or meanings.
```

- [ ] **Step 2: Replace optional inputs section**

Replace lines under `Optional user inputs:` with:

```markdown
Optional user inputs:
- any build intent that can be mapped to Jenkins parameter definitions
- missing required parameter values requested by the LLM after reading metadata
- confirmation to run the generated Jenkins CLI command
```

- [ ] **Step 3: Replace Trigger Workflow**

Replace entire `## Trigger Workflow (build/deploy)` section with:

```markdown
## Trigger Workflow (build/deploy)

1. Run `bin/jenkins-skill context` to verify git repo state and derive git host, branch, and Jenkins job path.
2. If helper output says the remote host is unsupported or the remote URL cannot be parsed, refuse and explain why.
3. Run `bin/jenkins-skill runtime` to resolve runtime root and required files.
4. If helper output shows missing runtime files, stop and tell the user which path is missing.
5. Run `bin/jenkins-skill metadata` to load branch, job path, Jenkins host, runtime root, and complete `parameters` definitions.
6. Read every parameter definition before deciding build parameters. Use `name`, `description`, `required`, `default`, and `availableValues` to infer values from user intent.
7. Do not use parameter names or business meanings that are not present in `metadata.parameters`.
8. For required parameters with no clear value or default, ask the user to choose or provide a value.
9. For ambiguous user intent, ask one focused question instead of guessing.
10. Build explicit `name=value` pairs only after all required values are known.
11. Run `bin/jenkins-skill trigger-command --param Name=value ...` to generate the Jenkins CLI argv and validate parameter names.
12. Present job path, final parameters, and full Jenkins CLI command to the user.
13. Trigger the Jenkins build with the generated Jenkins CLI command only after explicit user confirmation.
14. Poll the job JSON API until `lastBuild.number` increases.
15. Treat that new build number as the triggered build.
16. Poll the build API every 10–15 seconds until terminal state.
17. On failure, run `bin/jenkins-skill console-log` to fetch console tail and classify the failure.
```

- [ ] **Step 4: Replace Parameter Rules section**

Replace entire `## Parameter Rules` section with:

```markdown
## Parameter Rules

The parameter definitions returned by `bin/jenkins-skill metadata` are the source of truth.

For each parameter:
- `name` is the exact Jenkins parameter key.
- `description` explains the business meaning.
- `required` tells whether the build needs a value.
- `default` can be used when user intent does not override it.
- `availableValues` lists valid choices when present.

LLM responsibilities:
- map user intent to parameters by reading descriptions and choices
- use current git branch when a parameter definition clearly asks for branch
- use defaults when they satisfy intent and no user override exists
- ask the user when required values are missing or ambiguous
- pass only parameter names that exist in metadata

Do not hardcode rules for specific names like `OperatingEnvs`, `OperationType`, `DeployMicroServices`, `Namespace`, or `AdditionalOps`. These names may appear in one team's config, but they are examples, not workflow rules.
```

- [ ] **Step 5: Update failure handling**

In `## Failure Handling`, replace parameter-specific bullets:

```markdown
- the target environment is missing or ambiguous
- the requested operation type is outside the allowed set
```

with:

```markdown
- required Jenkins parameters cannot be inferred from user intent or defaults
- user intent maps to multiple possible `availableValues` choices
- `trigger-command` rejects an unknown parameter name
```

---

### Task 4: Update reference and README docs

**Files:**
- Modify: `plugins/jenkins-skill/skills/jenkins-skill/reference.md`
- Modify: `plugins/jenkins-skill/README.md`

- [ ] **Step 1: Update reference parameter mapping**

In `reference.md`, replace `## Parameter mapping` table with:

```markdown
## Parameter interpretation

`parameters` is metadata for LLM-driven build assembly. The helper returns it as-is through `bin/jenkins-skill metadata`.

| Field | Rule |
| --- | --- |
| `name` | exact Jenkins parameter key used in `-p name=value` |
| `description` | business meaning used by the LLM to map user intent |
| `required` | if true and no value/default can be inferred, ask the user |
| `default` | default value the LLM may use when intent does not override it |
| `availableValues` | valid choices; use `value` as machine choice and `description` for user-facing meaning |

The sample names `GitBranch`, `OperatingEnvs`, `OperationType`, `DeployMicroServices`, `Namespace`, and `AdditionalOps` are examples only. Skill workflow must not depend on those exact names.
```

- [ ] **Step 2: Add helper command reference**

In `reference.md`, add after `## Jenkins fields`:

```markdown
## Helper commands

- `bin/jenkins-skill context` — derive git host, branch, project, and Jenkins job path.
- `bin/jenkins-skill runtime` — validate runtime files and Jenkins host/auth configuration.
- `bin/jenkins-skill metadata` — output context, runtime metadata, job path, host, and all Jenkins parameter definitions.
- `bin/jenkins-skill trigger-command --param Name=value ...` — validate explicit parameter names and output Jenkins CLI argv.
- `bin/jenkins-skill last-build` — read latest Jenkins build metadata.
- `bin/jenkins-skill console-log [--build-number N] [--tail 80]` — read console log text.
```

- [ ] **Step 3: Update README helper entrypoint list**

In `README.md`, replace the helper CLI entrypoint list with:

```markdown
Helper CLI entrypoint:
- `bin/jenkins-skill context`
- `bin/jenkins-skill runtime`
- `bin/jenkins-skill metadata`
- `bin/jenkins-skill trigger-command --param Name=value [--param Name=value ...]`
- `bin/jenkins-skill last-build`
- `bin/jenkins-skill console-log [--build-number N] [--tail 80]`
- Python implementation: `bin/jenkins-skill`
```

- [ ] **Step 4: Replace README helper responsibilities**

Replace helper responsibilities with:

```markdown
Helper responsibilities:
- `context` derives git host, branch, and Jenkins job path
- `runtime` validates `jenkins-cli.jar` and `index.json`, then reports Jenkins host from config
- `metadata` returns complete Jenkins parameter definitions for LLM-driven assembly
- `trigger-command` validates explicit parameter names and emits the Jenkins CLI command argv
- `last-build` and `console-log` support build monitoring and failure diagnosis
```

- [ ] **Step 5: Replace README Config semantics section**

Replace `## Config semantics` content with:

```markdown
## Config semantics

`index.json` parameter definitions are metadata for the LLM. The helper does not hardcode business parameters.

For every parameter:
- `name` is the exact Jenkins parameter key.
- `description` explains how to choose the value from user intent.
- `required` means the LLM must supply a value or ask the user.
- `default` may be used when user intent does not override it.
- `availableValues` constrains choices when present.

Recommended operator flow:
1. run `bin/jenkins-skill metadata`
2. let the LLM assemble `name=value` pairs from user intent and parameter definitions
3. ask the user for missing or ambiguous required values
4. run `bin/jenkins-skill trigger-command --param Name=value ...`
5. confirm returned command with the user
6. execute the Jenkins CLI command after confirmation
```

---

### Task 5: Run full verification and inspect diff

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run unit tests**

Run:

```bash
python3 -m unittest "plugins/jenkins-skill/tests/test_jenkins_skill.py"
```

Expected:

```text
OK
```

- [ ] **Step 2: Verify helper command behavior manually**

Run tests already cover temp repos. No live Jenkins calls are required. Do not run generated Jenkins CLI command in verification.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff -- plugins/jenkins-skill/bin/jenkins-skill plugins/jenkins-skill/tests/test_jenkins_skill.py plugins/jenkins-skill/skills/jenkins-skill/SKILL.md plugins/jenkins-skill/skills/jenkins-skill/reference.md plugins/jenkins-skill/README.md
```

Expected:
- `params` command removed.
- `metadata` and `trigger-command` added.
- Skill docs no longer hardcode build parameter names as workflow rules.
- README/reference describe metadata-driven LLM assembly.

- [ ] **Step 4: Check working tree**

Run:

```bash
git status --short
```

Expected:
- Only intended files changed plus this plan file.
- No generated cache files staged or required.

---

## Self-Review

- Spec coverage: user intent → metadata → LLM parameter assembly → missing-value questions → confirmation → Jenkins CLI execution is covered by Tasks 2-4.
- Placeholder scan: no TBD/TODO/fill-later steps remain.
- Type consistency: helper command names are consistently `metadata` and `trigger-command`; parameter values are consistently passed as repeated `--param Name=value`.
