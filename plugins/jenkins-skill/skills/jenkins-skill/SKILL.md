---
name: jenkins-skill
description: Use when the user wants to trigger, monitor, or diagnose a Jenkins build or deploy for the current repository hosted on git.example.com.
---

# Jenkins Skill

## Overview

Natural-language Jenkins workflow for repos on `git.example.com`. Use helper CLI output for deterministic context, runtime, and parameter resolution; reserve LLM flow for clarifying input, confirmation, monitoring, and failure explanation.

## When to Use

- User wants to deploy the current repo through Jenkins
- User asks to trigger a build for the current branch
- User asks to inspect Jenkins results for the current project
- User asks to diagnose a failing Jenkins deployment for the current repo

Do not use when the current repo is not on `git.example.com`.

## Inputs

Required runtime context:
- current directory is a git repo
- `origin` remote exists
- current branch exists
- remote host is `git.example.com`

Required local configuration:
- runtime root = `JENKINS_SKILL_HOME` when set; otherwise default to `$HOME/.agentic-house/jenkins-skill`
- `${runtime root}/jenkins-cli.jar`
- `${runtime root}/index.json`
- helper entrypoint: `bin/jenkins-skill`
- local tools: `git`, `java`, `curl`, `python3`

Optional user inputs:
- target environment: `local` or `global`
- app list for `DeployMicroServices`
- `Namespace`
- operation type override

## Quick Operations

For viewing or diagnosing builds, prefer the helper CLI commands below. They handle URL construction, authentication, and response parsing internally — do NOT make manual Jenkins API calls for these operations.

### View latest build

1. Run `bin/jenkins-skill last-build` — single call, outputs structured JSON.
2. On success, format the result for the user:
   - build number, result, branch, environment, services, builder, duration, URL.
3. On error (missing config, auth failure, no builds), relay the error message.

### View console log (for failure diagnosis)

1. Run `bin/jenkins-skill console-log [--build-number N] [--tail 80]` — single call.
2. `--build-number` defaults to the last build if omitted.
3. Use the returned `log` field to classify the failure.

### Detect branch mismatch

After `last-build`, compare its `parameters` against the current git branch. If the last build was for a different branch, mention this to the user.

## Trigger Workflow (build/deploy)

1. Run `bin/jenkins-skill context` to verify git repo state and derive git host, branch, and Jenkins job path.
2. If helper output says the remote host is unsupported or the remote URL cannot be parsed, refuse and explain why.
3. If host is not supported, refuse and explain that this skill only supports repos from `git.example.com`.
4. Run `bin/jenkins-skill runtime` to resolve the runtime root and required files.
5. If helper output shows missing runtime files, stop and tell the user which path is missing.
6. Read Jenkins `host` and `auth` from `${runtime root}/index.json`.
7. Run `bin/jenkins-skill params ...` to resolve build parameters.
8. If helper output says environment or operation type is invalid, stop and ask the user instead of guessing.
9. Before triggering any build or deploy, present the derived job path and final parameters, then ask for explicit user confirmation.
10. Use helper output as the source of truth for deterministic values.
11. Fetch current `lastBuild.number` for the derived job through the authenticated Jenkins JSON API.
12. Trigger the Jenkins build with `jenkins-cli.jar` only after user confirmation.
13. Poll the job JSON API until `lastBuild.number` increases.
14. Treat that new build number as the triggered build.
15. Poll the build API every 10–15 seconds until terminal state.
16. On failure, run `bin/jenkins-skill console-log` to fetch console tail and classify the failure.

## Parameter Rules

Always derive or send:
- `GitBranch` = current git branch
- `OperatingEnvs` = item chosen from `parameters[name=OperatingEnvs].availableValues`
- `OperationType` = explicit user input or `parameters[name=OperationType].default`
- `AdditionalOps` = `parameters[name=AdditionalOps].default` or empty string

Optional parameters:
- `DeployMicroServices` = comma-separated app names when the user specifies apps; otherwise use `parameters[name=DeployMicroServices].default`
- `Namespace` = only include when user explicitly supplies it unless `parameters[name=Namespace].required = true`

## Failure Handling

Stop and ask the user instead of guessing when:
- the current directory is not a git repo
- `origin` remote is missing
- the remote host is not `git.example.com`
- the remote URL cannot be parsed into `group/project`
- the current branch is empty
- the runtime root or any required runtime file is missing
- `index.json` does not contain usable Jenkins `host` or `auth`
- the target environment is missing or ambiguous
- the requested operation type is outside the allowed set
- Jenkins auth, job lookup, or build-number discovery fails
- the triggered build number cannot be determined safely

Never guess values that are not defined by this skill.

## Failure Classification

When the build fails, classify into one of:

1. `infrastructure`
   - Jenkins unavailable, auth failures, agent offline
   - Docker, node, pod, or network provisioning failures
   - SCM fetch, workspace, disk, or timeout failures before app build logic
2. `business code error`
   - compile, test, lint, package, migration, app startup, or config errors caused by repo changes
3. `other`
   - manual aborts, ambiguous plugin failures, or insufficient signal

Failure response must always include Jenkins build URL.

## Outputs

On success, include:
- job path
- branch
- env
- operation type
- apps or all
- Jenkins build URL
- short status summary

On failure, include:
- classification (`infrastructure` / `business code error` / `other`)
- likely reason in 1–2 lines
- Jenkins build URL
- next-action hint for dev-side fix vs CI/platform follow-up
