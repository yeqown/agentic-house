---
name: jenkins
description: Trigger, monitor, or diagnose Jenkins builds and deploys for the current repository on git.example.com. Use when user wants to deploy, trigger a build, check build status, view console logs, or diagnose deployment failures.
---

# Jenkins Skill

Natural-language Jenkins workflow for repos on `git.example.com`. Uses helper CLI for deterministic git/runtime/Jenkins metadata. LLM maps user build intent to Jenkins parameters from definitions returned by `helper.py metadata`.

## Runtime Setup

- Runtime root: `JENKINS_SKILL_HOME` env var, or fallback `$HOME/.agentic-house/jenkins-skill`
- Required files: `jenkins-cli.jar`, `index.json`
- Helper: `./skills/jenkins/scripts/helper.py`
- Local tools: `git`, `java`, `curl`, `python3`
- All helper commands run from project root

Config schema, parameter rules, failure classification → [reference.md](reference.md)

## When to Use

- Deploy current repo through Jenkins
- Trigger build for current branch
- Inspect Jenkins results
- Diagnose failing Jenkins deployment

Do not use when the repo is not on `git.example.com`.

## Quick Operations

### View latest build

```bash
./skills/jenkins/scripts/helper.py last-build
```

On success, format: build number, result, branch, builder, duration, URL. On error, relay the message.

After `last-build`, compare its `parameters` against current git branch. If different branch, mention to user.

### View console log

```bash
./skills/jenkins/scripts/helper.py console-log [--build-number N] [--tail 80]
```

`--build-number` defaults to last build. Use returned `log` field to classify failure.

### View actual Jenkins job parameters

```bash
./skills/jenkins/scripts/helper.py job-parameters
```

Use when local metadata may be stale, incomplete, or missing candidate values. Treat returned `parameters` as Jenkins truth.

## Trigger Workflow (build/deploy)

1. Run `./skills/jenkins/scripts/helper.py metadata` — validates git repo, resolves config, derives job path, loads parameter definitions.
2. If helper reports unsupported remote, unparseable URL, or invalid config → stop and explain error.
3. Read every parameter definition. Use `name`, `description`, `required`, `default`, `availableValues` to infer values from user intent.
4. If `metadata.parameters` appears stale or conflicts → run `job-parameters` and prefer its result.
5. If user asks for "all"/"all services"/"full rollout" and metadata lacks complete candidate values → run `job-parameters` first.
6. Do not use parameter names or meanings not present in metadata or Jenkins job definitions.
7. For required parameters with no clear value/default → ask user to choose.
8. For ambiguous intent → ask one focused question, not guess.
9. Build explicit `name=value` pairs only after all required values are known.
10. Run `./skills/jenkins/scripts/helper.py trigger-command --param Name=value ...` to generate CLI argv and validate parameter names.
11. Present job path, final parameters, and full CLI command to user.
12. Trigger only after explicit user confirmation.
13. Poll job JSON API until `lastBuild.number` increases, then track that build to terminal state.
14. On failure → run `console-log --build-number <N>` to fetch log tail and classify.

## LLM Parameter Responsibilities

- Map user intent to parameters by reading descriptions and choices
- Use current git branch when a parameter definition clearly asks for branch
- Use defaults when they satisfy intent and no user override exists
- Ask user when required values are missing or ambiguous
- Pass only parameter names that exist in metadata or Jenkins definitions

Do not hardcode rules for specific names like `OperatingEnvs`, `OperationType`, `DeployMicroServices`. These are examples, not workflow rules.

## Failure Handling

Stop and ask user when: not a git repo, `origin` missing, remote host not `git.example.com`, URL cannot parse to `group/project`, branch empty, runtime files missing, Jenkins auth/job lookup fails, required parameters cannot be inferred, or `trigger-command` rejects a parameter name.

Failure classification (infrastructure / business code error / other) → [reference.md](reference.md)

## Outputs

On success: job path, branch, resolved parameters, Jenkins build URL, short status summary.

On failure: classification, likely reason in 1–2 lines, Jenkins build URL, next-action hint.
