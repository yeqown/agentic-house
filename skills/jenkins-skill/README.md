# jenkins-skill plugin

Claude Code plugin for triggering and diagnosing Jenkins builds for repositories hosted on `git.example.com`.

## Runtime setup

Runtime root defaults to `$HOME/.agentic-house/jenkins-skill`. Optionally override it:

```bash
export JENKINS_SKILL_HOME="/path/to/jenkins-skill-runtime"
```

Required files inside the resolved runtime root:
- `jenkins-cli.jar`
- `index.json`

Example:

```bash
RUNTIME_ROOT="${JENKINS_SKILL_HOME:-$HOME/.agentic-house/jenkins-skill}"
mkdir -p "$RUNTIME_ROOT"
cp /path/to/jenkins-cli.jar "$RUNTIME_ROOT/jenkins-cli.jar"
cp skills/jenkins-skill/config-sample/index.json "$RUNTIME_ROOT/index.json"
```

`skills/jenkins-skill/config-sample/index.json` is sample runtime config. Copy it first, then set Jenkins `host`, `auth`, and parameter definitions for your team.

Helper CLI entrypoint:
- `bin/jenkins-skill context`
- `bin/jenkins-skill runtime`
- `bin/jenkins-skill metadata`
- `bin/jenkins-skill trigger-command --param Name=value [--param Name=value ...]`
- `bin/jenkins-skill last-build`
- `bin/jenkins-skill console-log [--build-number N] [--tail 80]`
- Python implementation: `bin/jenkins-skill`

Helper responsibilities:
- `context` derives git host, branch, and Jenkins job path
- `runtime` validates `jenkins-cli.jar` and `index.json`, then reports Jenkins host from config
- `metadata` returns complete Jenkins parameter definitions for LLM-driven assembly
- `trigger-command` validates explicit parameter names and emits the Jenkins CLI command argv
- `last-build` and `console-log` support build monitoring and failure diagnosis

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
