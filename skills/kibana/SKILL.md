---
name: kibana
description: Use when the user wants to search or view application logs in Kibana using natural language, e.g. "查看测试环境用户平台 user-svc 的日志" or "搜索最近 2 小时 gateway-svc 日志中包含 keyword 的日志".
---

# Kibana Log Skill

## Overview

Natural-language Kibana log search. Use script-provided Kibana context plus the user's raw request to let the LLM parse Discover state, then construct a Kibana Discover URL with the resolved index UUID and optionally open it in the browser.

## When to Use

- User wants to view logs for a specific service in a specific environment
- User asks to search logs with a keyword, time range, or other filters
- User mentions Kibana, 日志, log search, or log viewing
- User asks to list available Kibana indices or discover fields

Do not use when the user wants to tail local log files or query a database directly.

## Inputs

Required runtime context:
- user provides a natural-language request describing desired environment, index/business unit, time range, filters, or search logic

Required local configuration:
- runtime root = `KIBANA_LOG_SKILL_HOME` when set; otherwise default to `$HOME/.agentic-house/kibana-log`
- `${runtime root}/index.json` — common config (environments, fields, defaults)
- `${runtime root}/<env-key>.json` — per-environment config (host, indices)
- helper script = `scripts/load_kibana_context.py`
- local tools: `python3`, `open` (macOS) or `xdg-open` (Linux)

A sample config is provided at `skills/kibana/config-sample/`. Copy it to the runtime root and edit values.

Optional user inputs:
- KQL query text
- time range (e.g. "最近 2 小时", "last 1h", "今天")
- explicit filters
- columns / sort

## Config Structure

Two-layer config: one common file + one file per environment.

### index.json — common config

```json
{
  "environments": {
    "test": "测试环境，Kibana 部署在新加坡",
    "prod": "生产环境"
  },
  "fields": [
    {
      "fieldName": "kubernetes.container_name",
      "description": "应用/容器名称，用于按服务过滤日志",
      "displayDefault": true
    },
    {
      "fieldName": "message.level",
      "description": "日志等级，如 ERROR/WARN/INFO/DEBUG",
      "displayDefault": true
    },
    {
      "fieldName": "message.msg",
      "description": "日志消息体，用于关键词搜索",
      "displayDefault": true
    },
    {
      "fieldName": "@timestamp",
      "description": "日志事件时间戳",
      "displayDefault": false
    }
  ],
  "defaultTimeRange": "1h"
}
```

- `environments` — key 对应 `<env-key>.json` 文件名，value 是环境描述
- `fields` — ES 字段定义数组，每项含：
  - `fieldName` — ES 实际字段名
  - `description` — 字段含义
  - `displayDefault` — `true` 表示默认展示为 Kibana Discover 列，`false` 或缺省不展示
- `defaultTimeRange` — 默认时间范围，如 `1h`, `30m`, `2h`

### <env-key>.json — 环境配置

```json
{
  "host": "https://kibana.example.net/",
  "indices": {
    "example-portal": "用户平台（example-portal）日志索引",
    "example-payment": "支付系统日志索引"
  }
}
```

- `host` — Kibana base URL
- `indices` — key 是索引名称，value 是描述。不含 UUID，UUID 从 API 动态获取

## Kibana API

### API 1: List all index patterns → get UUID

```bash
curl -s '${HOST}/api/saved_objects/_find?fields=title&fields=type&fields=typeMeta&per_page=10000&type=index-pattern' \
  -H 'kbn-version: 7.17.12' \
  -H 'content-type: application/json'
```

Response:
```json
{
  "saved_objects": [
    {
      "id": "ef7b2550-d30f-11ef-9c9f-07d9d86326f2",
      "attributes": { "title": "example-portal*" }
    }
  ]
}
```

Use `id` as UUID, `attributes.title` (strip trailing `*`) as index name.

## URL Construction

### Base URL format

```
${HOST}/app/discover#/?_g=${RISON_GLOBAL_STATE}&_a=${RISON_APP_STATE}
```

### Discover state model

`_g`:
- `time`
- `refreshInterval`
- global `filters`

`_a`:
- `index`
- `columns`
- `sort`
- app `filters`
- `query`

### Columns

Derived from `fields` in `index.json`: collect all field entries where `displayDefault` is `true`, use their `fieldName` values as columns. Order follows the order in `fields` array.

### Filter object format

Each filter in the `filters` array:

```json
{
  "$state": { "store": "appState" },
  "meta": {
    "alias": null,
    "disabled": false,
    "index": "${INDEX_UUID}",
    "key": "${FIELD}",
    "negate": false,
    "params": { "query": "${VALUE}" },
    "type": "phrase"
  },
  "query": { "match_phrase": { "${FIELD}": "${VALUE}" } }
}
```

`meta.index` must be the same UUID as the top-level `index` param.

### Query vs filters

- `filters` 适合 exact/range/exists 等结构化约束
- `appState.query.query` 适合 OR / AND / 括号 / 文本搜索等 KQL 逻辑

## Core Workflow

### Standard log search flow

1. Read the user's natural-language request.
2. Run `python3 scripts/load_kibana_context.py context` from the skill directory first. It should resolve runtime root, load config, fetch live Kibana index metadata, and return environment info plus matched `indexName -> uuid` mappings.
3. Read the returned JSON.
4. Combine the raw user request with the context JSON and let the LLM parse these Discover state pieces:
   - `environment`
   - `indexName`
   - `indexUuid`
   - `globalState`
   - `appState.columns`
   - `appState.sort`
   - `appState.filters`
   - `appState.query`
5. If environment is missing or ambiguous, present options from the `environments` payload using `AskUserQuestion` instead of free-form input.
6. If business unit / index is missing or ambiguous, present options from the selected environment's configured indices using `AskUserQuestion` instead of free-form input.
7. If required state parts are missing, ask the user directly. Prefer choice-based interaction whenever the context payload provides clear options.
8. When required parameters are complete, run `python3 scripts/load_kibana_context.py build-url --payload-json '<json>'` from the skill directory with the resolved UUID.
9. Report the extracted parameters and final URL so the user can copy/paste.
10. Ask the user whether to open the URL.
11. Only after explicit approval, open the URL with `open` (macOS) or `xdg-open` (Linux). If open fails, say so clearly and still return the URL.

### Discovery-only flow (user asks to list indices)

1. Run `python3 scripts/load_kibana_context.py context` from the skill directory.
2. Read the returned environments and per-env `indices` mapping.
3. Present the list (`indexName -> UUID`) to the user.
4. If the user only wants one environment, prefer `context --env <env>`.

## Failure Handling

Stop and ask the user instead of guessing when:

- environment cannot be determined from the input and there are no clear configured options to present
- business unit cannot be matched to any configured index
- `KIBANA_LOG_SKILL_HOME` (or fallback) is unavailable
- `index.json` is missing or has no valid `environments` key
- `<env-key>.json` is missing for the requested environment
- Kibana API returns no match for the selected index name
- Kibana API returns 401/403 or other auth-related failure
- Kibana host is empty or malformed
- time range cannot be parsed by the LLM into explicit `from` / `to` values
- `build-url` payload is missing `host`, `indexUuid`, `globalState.time.from`, or `globalState.time.to`

Never guess values that are not defined by this skill.

## Outputs

On success, include:
- extracted parameters (env, index name, index UUID, time range, filters, query)
- resolved Kibana host
- full Kibana Discover URL
- whether the URL was opened automatically

On failure, include:
- which parameter is missing or ambiguous
- available environment or index options
- suggested fix
