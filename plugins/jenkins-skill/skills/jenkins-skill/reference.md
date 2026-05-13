# Jenkins Skill Reference

## Supported Git remotes

- `git@git.example.com:group/project.git`
- `https://git.example.com/group/project.git`
- `ssh://git@git.example.com[:port]/group/project.git`

Multi-level groups are supported (e.g., `team/backend/service-mono`).

Derived Jenkins job path:
- `group/project` (group may contain `/`)

Derived Jenkins job URL base:
- `${JENKINS_URL}/job/group/job/project/` (each path segment becomes `job/<segment>`)

## Jenkins runtime files

Runtime root selection:
- use `JENKINS_SKILL_HOME` when set
- otherwise use `$HOME/.agentic-house/jenkins-skill`

Required files inside the resolved runtime root:
- `jenkins-cli.jar` — Jenkins CLI jar
- `index.json` — team/project specific Jenkins config, including `host` and `auth`

Sample config:
- `plugins/jenkins-skill/config-sample/index.json`

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

## Jenkins fields

| Field | Rule |
| --- | --- |
| `host` | Jenkins base URL, for example `https://jenkins.example.net/` |
| `auth` | Jenkins auth in `username:api-token` format |

## Parameter schema

Each item in `parameters` must include:
- `name`
- `description`
- `required`

Optional fields:
- `default`
- `availableValues` — format: `[{"value":"...","description":"..."}]`

## Parameter mapping

| Name | Rule |
| --- | --- |
| `GitBranch` | value comes from current git branch |
| `OperatingEnvs` | selected value comes from `availableValues[].value`, payload uses matching `description` |
| `OperationType` | selected value comes from CLI or `default`, allowed set comes from `availableValues[].value` |
| `DeployMicroServices` | value comes from CLI or `default` |
| `Namespace` | omit unless user supplies one, or fail when `required = true` |
| `AdditionalOps` | value comes from `default` |

## Job path derivation

- Only `git.example.com` remotes are supported.
- Supported remote forms are `git@host:group/project.git` and `https://host/group/project.git`.
- Jenkins job path is always derived as `group/project` from git remote.
- Job path is not configurable.

## Failure hints

### infrastructure
- Jenkins unavailable or auth failure
- agent offline
- Docker, pod, node, or network provisioning failures
- SCM fetch, workspace, disk, or timeout failures before project build logic

### business code error
- compile, test, lint, or package failures
- config render or app startup issues caused by repo changes
- migration or deploy script failures owned by project code

### other
- manual aborts
- ambiguous plugin failures
- insufficient log signal to classify safely
