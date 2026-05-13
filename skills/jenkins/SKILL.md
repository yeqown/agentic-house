---
name: jenkins
description: Use when the user wants to trigger, monitor, or diagnose a Jenkins build or deploy for the current repository hosted on git.example.com.
---

# Jenkins Skill

## Overview

Natural-language Jenkins workflow for repos on `git.example.com`. Use helper CLI output for deterministic git/runtime/Jenkins metadata. The LLM must map user build intent to Jenkins parameters from the parameter definitions returned by `bin/jenkins-skill metadata`; helper code must not hardcode business parameter names or meanings.

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
- any build intent that can be mapped to Jenkins parameter definitions
- missing required parameter values requested by the LLM after reading metadata
- confirmation to run the generated Jenkins CLI command

## Quick Operations

For viewing or diagnosing builds, prefer the helper CLI commands below. They handle URL construction, authentication, and response parsing internally — do NOT make manual Jenkins API calls for these operations.

### View latest build

1. Run `bin/jenkins-skill last-build` — single call, outputs structured JSON.
2. On success, format the result for the user:
   - build number, result, branch/current parameters, builder, duration, URL.
3. On error (missing config, auth failure, no builds), relay the error message.

### View console log (for failure diagnosis)

1. Run `bin/jenkins-skill console-log [--build-number N] [--tail 80]` — single call.
2. `--build-number` defaults to the last build if omitted.
3. Use the returned `log` field to classify the failure.

### View actual Jenkins job parameters

1. Run `bin/jenkins-skill job-parameters` when local metadata may be stale, incomplete, or missing real candidate values.
2. Treat returned `parameters` as Jenkins truth for names, defaults, and `availableValues`.
3. If the command succeeds, prefer Jenkins values over `metadata.parameters` for any conflicting field.

### Detect branch mismatch

After `last-build`, compare its `parameters` against the current git branch. If the last build was for a different branch, mention this to the user.

## Trigger Workflow (build/deploy)

1. Run `bin/jenkins-skill context` to verify git repo state and derive git host, branch, and Jenkins job path.
2. If helper output says the remote host is unsupported or the remote URL cannot be parsed, refuse and explain why.
3. Run `bin/jenkins-skill runtime` to resolve runtime root and required files.
4. If helper output shows missing runtime files, stop and tell the user which path is missing.
5. Run `bin/jenkins-skill metadata` to load branch, job path, Jenkins host, runtime root, and complete `parameters` definitions.
6. Read every parameter definition before deciding build parameters. Use `name`, `description`, `required`, `default`, and `availableValues` to infer values from user intent.
7. If `metadata.parameters` appears stale, incomplete, or conflicts with Jenkins behavior, run `bin/jenkins-skill job-parameters` and treat its result as source of truth.
8. If the user asks for “all”, “all services”, “full rollout”, or similar intent and `metadata.parameters` does not provide complete candidate values, run `bin/jenkins-skill job-parameters` to fetch the actual Jenkins choice list before expanding values.
9. Do not use parameter names or business meanings that are not present in metadata or Jenkins job definitions.
10. For required parameters with no clear value or default, ask the user to choose or provide a value.
11. For ambiguous user intent, ask one focused question instead of guessing.
12. Build explicit `name=value` pairs only after all required values are known.
13. Run `bin/jenkins-skill trigger-command --param Name=value ...` to generate the Jenkins CLI argv and validate parameter names.
14. Present job path, final parameters, and full Jenkins CLI command to the user.
15. Trigger the Jenkins build with the generated Jenkins CLI command only after explicit user confirmation.
16. Use the authenticated Jenkins JSON API for polling here because no helper command currently triggers or monitors newly queued builds.
17. Poll the job JSON API until `lastBuild.number` increases.
18. Treat that new build number as the triggered build.
19. Poll the build API every 10–15 seconds until terminal state.
20. On failure, run `bin/jenkins-skill console-log --build-number <triggered build number>` to fetch console tail and classify the failure.

## Parameter Rules

The parameter definitions returned by `bin/jenkins-skill metadata` are the default starting point.

`metadata.parameters` is local guidance, not guaranteed Jenkins truth. When Jenkins job definitions disagree with local metadata or local metadata lacks enough candidate values to satisfy user intent, run `bin/jenkins-skill job-parameters` and prefer its returned fields for `name`, `default`, and `availableValues`.

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
- pass only parameter names that exist in metadata or Jenkins job definitions

Do not hardcode rules for specific names like `OperatingEnvs`, `OperationType`, `DeployMicroServices`, `Namespace`, or `AdditionalOps`. These names may appear in one team's config, but they are examples, not workflow rules.

## Failure Handling

Stop and ask the user instead of guessing when:
- the current directory is not a git repo
- `origin` remote is missing
- the remote host is not `git.example.com`
- the remote URL cannot be parsed into `group/project`
- the current branch is empty
- the runtime root or any required runtime file is missing
- `index.json` does not contain usable Jenkins `host` or `auth`
- required Jenkins parameters cannot be inferred from user intent or defaults
- user intent maps to multiple possible `availableValues` choices
- `trigger-command` rejects an unknown parameter name
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
- resolved Jenkins parameters
- Jenkins build URL
- short status summary

On failure, include:
- classification (`infrastructure` / `business code error` / `other`)
- likely reason in 1–2 lines
- Jenkins build URL
- next-action hint for dev-side fix vs CI/platform follow-up
