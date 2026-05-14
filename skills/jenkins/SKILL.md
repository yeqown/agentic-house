---
name: jenkins
description: Trigger, monitor, or diagnose Jenkins builds and deploys for the current repository on git.example.com. Use when user wants to deploy, trigger a build, check build status, view console logs, or diagnose deployment failures.
---

# Jenkins Skill

Natural-language Jenkins workflow for repos on `git.example.com`.

## Pattern Contract

- Tool wrapper: `./skills/jenkins/scripts/helper.py` owns git context, runtime config, Jenkins API reads, and Jenkins CLI argv construction.
- Generator: `metadata`, `job-parameters`, and `trigger-command` generate structured JSON that the LLM must reuse, not re-create from memory.
- Reviewer: `last-build` and `console-log` provide evidence for classifying failures.
- Reversal interview: ask the user for missing required values, ambiguous choices, and trigger confirmation before shared Jenkins state changes.
- Pipeline: follow workflow steps in order; do not skip, repeat, or reorder preflight, generation, confirmation, execution, or diagnosis.

## Runtime Setup

- Runtime root: `JENKINS_SKILL_HOME` env var, or fallback `$HOME/.agentic-house/jenkins-skill`
- Required files: `jenkins-cli.jar`, `index.json`
- Helper: `./skills/jenkins/scripts/helper.py`
- Local tools: `git`, `java`, `curl`, `python3`
- All helper commands run from project root

Config schema, helper contracts, parameter rules, failure classification → [reference.md](reference.md)

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

1. Preflight: run `./skills/jenkins/scripts/helper.py metadata` exactly once.
2. Stop if metadata reports unsupported remote, unparseable URL, invalid config, missing runtime file, or empty parameter list.
3. Read every returned parameter definition before deciding values: `name`, `description`, `required`, `default`, `availableValues`.
4. If metadata appears stale or lacks candidate values needed for user intent, run `./skills/jenkins/scripts/helper.py job-parameters` once and use its `parameters` as the active parameter source.
5. Reversal interview: ask one focused question for missing required values, ambiguous environment/service/action, or user intent that cannot be mapped from active parameters.
6. Build explicit `name=value` pairs only from active parameter definitions.
7. Generate command with `./skills/jenkins/scripts/helper.py trigger-command --job-path <jobPath> --available-param <name> ... --param Name=value ...`.
8. Present job path, active parameter source (`metadata` or `job-parameters`), final parameters, and full CLI command.
9. Reversal confirmation: trigger only after explicit user approval.
10. After triggering, poll job JSON API until `lastBuild.number` increases, then track that build to terminal state.
11. Reviewer path: on failure, run `./skills/jenkins/scripts/helper.py console-log --build-number <N>` and classify with the failure rubric.

## LLM Parameter Responsibilities

- Map user intent to parameters by reading descriptions and choices
- Use current git branch when a parameter definition clearly asks for branch
- Use defaults when they satisfy intent and no user override exists
- Ask user when required values are missing or ambiguous
- Pass only parameter names that exist in metadata or Jenkins definitions

Do not hardcode rules for specific names like `OperatingEnvs`, `OperationType`, `DeployMicroServices`. These are examples, not workflow rules.

## Failure Handling

Stop and ask user when: not a git repo, `origin` missing, remote host not `git.example.com`, URL cannot parse to `group/project`, branch empty, runtime files missing, Jenkins auth/job lookup fails, required parameters cannot be inferred, or `trigger-command` rejects a parameter name.

Reviewer rubric → [reference.md](reference.md). Use fetched build metadata and console log evidence only; do not classify from status alone.

## Outputs

On success: job path, branch, resolved parameters, Jenkins build URL, short status summary.

On failure: classification, likely reason in 1–2 lines, Jenkins build URL, next-action hint.
