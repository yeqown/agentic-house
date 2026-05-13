# jenkins-skill plugin

Claude Code plugin for triggering and diagnosing Jenkins builds for repositories hosted on `git.example.com`.

## Runtime setup

Set one environment variable:

```bash
export JENKINS_SKILL_HOME="$HOME/.agentic-house/jenkins-skill"
```

Required files inside `JENKINS_SKILL_HOME`:
- `jenkins-cli.jar`
- `index.json`

Example:

```bash
mkdir -p "$JENKINS_SKILL_HOME"
cp /path/to/jenkins-cli.jar "$JENKINS_SKILL_HOME/jenkins-cli.jar"
cp plugins/jenkins-skill/config-sample/index.json "$JENKINS_SKILL_HOME/index.json"
```

`plugins/jenkins-skill/config-sample/index.json` is sample runtime config. Copy it first, then set Jenkins `host`, `auth`, and parameter definitions for your team.

Helper CLI entrypoint:
- `bin/jenkins-skill context`
- `bin/jenkins-skill runtime`
- `bin/jenkins-skill params --env local [--operation-type FullDeploy] [--services svc-a,svc-b] [--namespace ns]`
- Python implementation: `bin/jenkins-skill`

Helper responsibilities:
- `context` derives git host, branch, and Jenkins job path
- `runtime` validates `jenkins-cli.jar` and `index.json`, then reports Jenkins host from config
- `params` builds Jenkins parameters from `index.json` and user input

## Local plugin development

```bash
claude --plugin-dir /absolute/path/to/agentic-house/plugins/jenkins-skill
```

## Tests

```bash
bash tests/claude-code/run-skill-tests.sh
```
