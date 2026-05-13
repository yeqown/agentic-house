---
name: kibana
description: Search and view application logs in Kibana using natural language. Use when user mentions Kibana, 日志/log search, or wants to filter logs by service, environment, time range, or keyword. Triggers include "查看日志", "search logs", "Kibana discover", "查看环境日志".
---

# Kibana Log Skill

Natural-language Kibana log search. Uses a two-phase flow: load context (env/host/fields/index-UUID mapping), then let LLM parse Discover state and build a Kibana Discover URL.

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

1. Run `python3 scripts/load_kibana_context.py context` from skill directory.
2. Read returned JSON — contains environments, fields, defaultTimeRange, per-env host, and `indexName -> uuid` mapping.
3. Combine user request + context JSON, let LLM parse these Discover state pieces:
   - `environment`, `indexName`, `indexUuid`
   - `globalState` (time)
   - `appState` (columns, sort, filters, query)
4. If environment is missing/ambiguous → present options from `environments` payload via `AskUserQuestion`.
5. If index is missing/ambiguous → present options from selected environment's `indices` via `AskUserQuestion`.
6. When required parameters are complete, run:
   ```bash
   python3 scripts/load_kibana_context.py build-url --payload-json '<json>'
   ```
   See [reference.md](reference.md) for required/optional payload fields.
7. Report extracted parameters and final URL.
8. Ask user whether to open the URL. Only after explicit approval, open with `open`/`xdg-open`. If open fails, return URL anyway.

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

Never guess values not defined by this skill.

## Outputs

On success: extracted parameters, resolved host, full Kibana Discover URL, whether URL was opened.

On failure: which parameter is missing/ambiguous, available options, suggested fix.
