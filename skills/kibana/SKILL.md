---
name: kibana
description: Use when the user wants to search or view application logs in Kibana using natural language, e.g. "查看测试环境用户平台 user-svc 的日志" or "搜索最近 2 小时 gateway-svc 日志中包含 keyword 的日志".
---

# Kibana Log Skill

## Overview

Natural-language Kibana log search. Parse user intent into structured query parameters, discover index UUID via Kibana API, construct a Kibana Discover URL, and open it in the browser.

## When to Use

- User wants to view logs for a specific service in a specific environment
- User asks to search logs with a keyword, time range, or other filters
- User mentions Kibana, 日志, log search, or log viewing
- User asks to list available Kibana indices or discover fields

Do not use when the user wants to tail local log files or query a database directly.

## Inputs

Required runtime context:
- user provides at minimum: environment, business unit (or index), and service name

Required local configuration:
- runtime root = `KIBANA_LOG_SKILL_HOME` when set; otherwise default to `$HOME/.agentic-house/kibana-log`
- `${runtime root}/index.json` — common config (environments, fields, defaults)
- `${runtime root}/<env-key>.json` — per-environment config (host, indices)
- `load_kibana_context.py` — helper loader that emits one JSON context bundle for the model
- local tools: `curl`, `jq`, `open` (macOS) or `xdg-open` (Linux)

A sample config is provided at `skills/kibana/config-sample/`. Copy it to the runtime root and edit values.

Optional user inputs:
- keyword / search term
- time range (e.g. "最近 2 小时", "last 1h", "今天")
- namespace or pod name
- log level (ERROR, WARN, INFO, DEBUG)

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

### \<env-key\>.json — 环境配置

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

**LLM workflow**: run this command, parse JSON, match index name from config to `title` field, extract `id` as UUID.

### API 2: List fields in an index

```bash
curl -s '${HOST}/api/index_patterns/_fields_for_wildcard?pattern=${INDEX_NAME}*&meta_fields=_source&meta_fields=_id&meta_fields=_type&meta_fields=_index&meta_fields=_score' \
  -H 'kbn-version: 7.17.12' \
  -H 'content-type: application/json'
```

Response:
```json
{
  "fields": {
    "kubernetes.container_name": { "type": "string", "searchable": true },
    "message.level": { "type": "string" },
    "message.msg": { "type": "string" }
  }
}
```

Use to validate that configured field names exist in the index.

## Parameter Extraction Rules

| Field | Extraction Rule | Default |
| --- | --- | --- |
| `environment` | 测试/测试环境/test/staging = `test`; 生产/线上/prod/production = `prod`; 预发/pre/preprod = `pre` | required |
| `businessUnit` | Match against `indices` keys and values in `<env-key>.json` | required |
| `service` | Application / container name (filter on `fields[].fieldName` where entry matches container) | required |
| `keyword` | Phrases after 包含/关键词/search/keyword | empty |
| `timeRange` | 最近N小时→`now-Nh`, 最近N分钟→`now-Nm`, 今天→`now/d` | `now-${defaultTimeRange}` to `now` |
| `namespace` | Match after namespace/命名空间 | omit |
| `logLevel` | ERROR/错误, WARN/警告, INFO/信息, DEBUG/调试 | omit |

## URL Construction

### Base URL format

```
${HOST}/app/discover#/
  ?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:'${FROM}',to:'${TO}'))
  &_a=(columns:!(${COLUMNS}),filters:${FILTERS_JSON},index:'${INDEX_UUID}',interval:auto,query:(language:kuery,query:'${QUERY}'),sort:!(!('${TIMESTAMP}',desc)))
```

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

### Filter field mapping

- service → `fields[].fieldName` where description matches container (e.g. `kubernetes.container_name`)
- log level → `fields[].fieldName` where description matches log level (e.g. `message.level`)

Keyword goes into `query` field as KQL: `${message field fieldName}:"${KEYWORD}"` or `*` if empty.

## Core Workflow

### Standard log search flow

1. Read the user's natural language request.
2. Run `load_kibana_context.py` first. It should resolve runtime root, load config, parse intent, prepare candidates, and build `urlSkeleton` with `__INDEX_UUID__` placeholder in one shot.
3. Read the returned JSON.
4. If environment is missing or ambiguous, present environment options from `candidates.environment` using `AskUserQuestion` instead of free-form input.
5. If business unit / index is missing or ambiguous, present `candidates.indexName` using `AskUserQuestion` instead of free-form input.
6. If service name is missing or ambiguous, ask with `AskUserQuestion` whenever `candidates.service` or other clear options are available. Prefer choice-based interaction over free-form input whenever possible.
7. After user fills missing values, re-run `load_kibana_context.py` with override flags such as `--env`, `--index`, `--service`.
8. **Fetch UUID from API**: run curl command (API 1) against the resolved Kibana host.
9. Parse response, match resolved index name against `saved_objects[].attributes.title` (strip trailing `*`).
10. Extract `id` as UUID. If no match found, stop and list available indices to the user.
11. **Optional field validation**: run API 2, check that configured field names exist in the index. Warn if missing.
12. Replace `__INDEX_UUID__` inside `urlSkeleton` with the resolved UUID to produce the final URL.
13. Report the extracted parameters and final URL so the user can copy/paste.
14. Ask the user whether to open the URL.
15. Only after explicit approval, open the URL with `open` (macOS) or `xdg-open` (Linux). If open fails, say so clearly and still return the URL.

### Discovery-only flow (user asks to list indices)

1. Read environment from user input.
2. Load `index.json` and `<env-key>.json`.
3. Run API 1, list all index patterns.
4. Present the list (name + UUID) to the user.
5. Optionally call API 2 for a specific index if user asks about fields.

## Failure Handling

Stop and ask the user instead of guessing when:

- environment cannot be determined from the input and there are no clear configured options to present
- business unit cannot be matched to any index
- service name cannot be determined from the input and there are no clear candidate choices to present
- `KIBANA_LOG_SKILL_HOME` (or fallback) is unavailable
- `index.json` is missing or has no `environments` key
- `<env-key>.json` is missing for the resolved environment
- API 1 returns no match for the index name
- Kibana API returns 401/403 or other auth-related failure
- Kibana host is empty or malformed
- time range cannot be parsed

Never guess values that are not defined by this skill.

## Outputs

On success, include:
- extracted parameters (env, business unit, index name, index UUID, service, keyword, time range)
- resolved Kibana host
- full Kibana Discover URL
- whether the URL was opened automatically

On failure, include:
- which parameter is missing or ambiguous
- available indices (if API was called)
- suggested fix
