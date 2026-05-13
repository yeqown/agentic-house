# Jenkins Skill Reference

## 目录

- Supported Git remotes
- Runtime files
- index.json schema
- Helper commands
- Parameter schema
- Parameter interpretation rules
- Job path derivation
- Failure classification

## Supported Git remotes

- `git@git.example.com:group/project.git`
- `https://git.example.com/group/project.git`
- `ssh://git@git.example.com[:port]/group/project.git`

Multi-level groups supported (e.g. `team/backend/service-mono`).

## Runtime files

Runtime root: `JENKINS_SKILL_HOME` when set, otherwise `$HOME/.agentic-house/jenkins-skill`

Required files:
- `jenkins-cli.jar` — Jenkins CLI
- `index.json` — project-specific config (host, auth, parameters)

Sample: `skills/jenkins/config-sample/index.json`

## index.json schema

```json
{
  "host": "https://jenkins.example.net/",
  "auth": "username:api-token",
  "parameters": [
    {
      "name": "GitBranch",
      "description": "Current git branch name sent to Jenkins.",
      "required": true,
      "default": "git.branch"
    },
    {
      "name": "OperatingEnvs",
      "description": "Target runtime environment.",
      "required": true,
      "availableValues": [
        { "value": "local", "description": "测试环境 local01" },
        { "value": "global", "description": "测试环境 global" }
      ]
    },
    {
      "name": "OperationType",
      "description": "Jenkins operation type.",
      "required": true,
      "default": "FullDeploy",
      "availableValues": [
        { "value": "FullDeploy", "description": "Full deploy flow." },
        { "value": "BuildForProd", "description": "Build artifacts for production." },
        { "value": "UpdateConfigMapAndRestart", "description": "Update config and restart workload." },
        { "value": "UpdateManifestWithoutWorkload", "description": "Update manifest without workload rollout." },
        { "value": "Reconfig", "description": "Reapply runtime config." }
      ]
    },
    {
      "name": "DeployMicroServices",
      "description": "Comma-separated service list; empty means all services.",
      "required": true,
      "default": ""
    },
    {
      "name": "Namespace",
      "description": "Kubernetes namespace override.",
      "required": false
    },
    {
      "name": "AdditionalOps",
      "description": "Additional Jenkins operation flags.",
      "required": true,
      "default": ""
    }
  ]
}
```

| Field | Rule |
| --- | --- |
| `host` | Jenkins base URL, e.g. `https://jenkins.example.net/` |
| `auth` | `username:api-token` format |

## Helper commands

All commands run from current project root.

| Command | Description |
| --- | --- |
| `./skills/jenkins/scripts/helper.py metadata` | Derive git context, validate runtime config, return merged parameter metadata |
| `./skills/jenkins/scripts/helper.py job-parameters` | Read actual Jenkins job parameter definitions and candidate values |
| `./skills/jenkins/scripts/helper.py trigger-command --param Name=value ...` | Validate parameter names, output Jenkins CLI argv |
| `./skills/jenkins/scripts/helper.py last-build` | Read latest build metadata |
| `./skills/jenkins/scripts/helper.py console-log [--build-number N] [--tail 80]` | Read console log text |

## Parameter schema

Each item in `parameters` must include:
- `name` — exact Jenkins parameter key
- `description` — business meaning
- `required` — whether build needs a value

Optional fields:
- `default` — fallback value
- `availableValues` — `[{"value":"...","description":"..."}]`

## Parameter interpretation rules

`parameters` is metadata for LLM-driven build assembly. `helper.py metadata` is the unified preflight command returning merged git/runtime/parameter payload.

`metadata.parameters` is local guidance, not guaranteed Jenkins truth. When Jenkins job definitions disagree with local metadata or local metadata lacks enough candidate values → run `job-parameters` and prefer its returned fields for `name`, `default`, and `availableValues`.

| Field | Rule |
| --- | --- |
| `name` | Exact Jenkins parameter key for `-p name=value` |
| `description` | Business meaning used by LLM to map user intent |
| `required` | If true and no value/default can be inferred, ask the user |
| `default` | Default value LLM may use when intent does not override |
| `availableValues` | Valid choices; `value` is machine choice, `description` is user-facing meaning |

The sample names `GitBranch`, `OperatingEnvs`, `OperationType`, `DeployMicroServices`, `Namespace`, `AdditionalOps` are examples only. Skill workflow must not depend on those exact names.

## Job path derivation

- Only `git.example.com` remotes are supported
- Helper derives host and job path from: `git@host:group/project.git`, `https://host/group/project.git`, `ssh://git@host[:port]/group/project.git`
- Jenkins job path: `group/project` (group may contain `/`)
- Job URL base: `${JENKINS_URL}/job/group/job/project/` (each segment becomes `job/<segment>`)
- Job path is not configurable

## Failure classification

### infrastructure
- Jenkins unavailable or auth failure
- Agent offline
- Docker, pod, node, or network provisioning failures
- SCM fetch, workspace, disk, or timeout failures before project build logic

### business code error
- Compile, test, lint, or package failures
- Config render or app startup issues caused by repo changes
- Migration or deploy script failures owned by project code

### other
- Manual aborts
- Ambiguous plugin failures
- Insufficient log signal to classify safely
