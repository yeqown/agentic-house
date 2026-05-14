---
name: kibana
description: Search and view application logs in Kibana using natural language. Use when user mentions Kibana, 日志/log search, or wants to filter logs by service, environment, time range, or keyword. Triggers include "查看日志", "search logs", "Kibana discover", "查看环境日志".
---

# Kibana Log Skill

Natural-language Kibana log search using deterministic context loading and Discover URL generation.

## Pattern Contract

- Tool wrapper: `python3 scripts/load_kibana_context.py context` owns runtime config, environment metadata, field metadata, host lookup, and index UUID mapping.
- Generator: `python3 scripts/load_kibana_context.py build-url --payload-json '<json>'` owns Rison encoding and final Discover URL construction.
- Reviewer: fetched or user-provided logs are scored by severity only after evidence exists.
- Reversal interview: ask the user for missing environment, index/service, time range, or ambiguous filters before URL generation.
- Pipeline: follow workflow steps in order; do not skip, repeat, or reorder context loading, state generation, URL generation, confirmation, or open action.

## Runtime Setup

- Runtime root: `KIBANA_LOG_SKILL_HOME` env var, or fallback `$HOME/.agentic-house/kibana-log`
- Required files: `index.json` (common config), `<env-key>.json` per environment
- Helper script: `scripts/load_kibana_context.py`
- Local tools: `python3`, `open` (macOS) / `xdg-open` (Linux)
- Sample config: `skills/kibana/config-sample/`

Config schema and API details → [reference.md](reference.md)

## User Inputs

Required: natural-language request describing environment, service/index, time range, or search filters.

Optional: KQL query text, explicit filters, columns, sort.

## Core Workflow

### Standard log search

1. Preflight: run `python3 scripts/load_kibana_context.py context` from skill directory exactly once.
2. Stop if context reports missing runtime root, missing config, malformed host, auth failure, or empty environments.
3. Read returned JSON before deciding values: `environments`, `fields`, `defaultTimeRange`, per-env host, and `indexName -> uuid` mapping.
4. Reversal interview: ask one focused question when environment, index/service, time range, or query filters are missing or ambiguous.
5. Generate Discover state JSON from user request plus context: `environment`, `indexName`, `indexUuid`, `globalState`, `appState`.
6. Run `python3 scripts/load_kibana_context.py build-url --payload-json '<json>'`.
7. Present extracted parameters, resolved host, query/filter summary, time range, and final URL.
8. Reversal confirmation: open URL only after explicit user approval.
9. Reviewer path: if user provides log output or asks for diagnosis, classify severity from evidence and list next action.

### Discovery-only (list indices)

1. Run `python3 scripts/load_kibana_context.py context [--env <env>]`.
2. Present `indexName -> UUID` mapping to user.

## Discover URL Structure

```
${HOST}/app/discover#/?_g=${RISON_GLOBAL_STATE}&_a=${RISON_APP_STATE}
```

State model and filter template → [reference.md](reference.md)

## Failure Handling

Stop and ask the user when: environment or index cannot be determined, runtime root or config files are missing, Kibana API returns no match / auth failure / malformed host, time range cannot be parsed, or required `build-url` payload fields are missing.

Reviewer rubric → [reference.md](reference.md). Use actual log lines or helper errors as evidence; do not classify severity from query intent alone.

Use only values defined by this skill.

## Outputs

On success: extracted parameters, resolved host, full Kibana Discover URL, whether URL was opened.

On failure: which parameter is missing/ambiguous, available options, suggested fix.
