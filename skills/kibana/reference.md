# Kibana Log Skill Reference

## Config file layout

```
$HOME/.agentic-house/kibana-log/
├── index.json        # 通用配置（环境列表、字段定义、默认值）
├── test.json         # 测试环境（host、indices）
├── prod.json         # 生产环境
└── pre.json          # 预发环境（可选）
```

Sample config: `skills/kibana/config-sample/`

## index.json

```json
{
  "environments": { "<env-key>": "<环境描述>" },
  "fields": [
    {
      "fieldName": "<ES 字段名>",
      "description": "<含义>",
      "displayDefault": true
    }
  ],
  "defaultTimeRange": "<如 1h>"
}
```

- `displayDefault` — `true` 表示默认展示为 Discover 列，`false` 或缺省不展示

### fields 示例

| fieldName | displayDefault | 含义 |
|---|---|---|
| `kubernetes.container_name` | `true` | 应用/容器名 |
| `message.level` | `true` | 日志等级 |
| `message.msg` | `true` | 日志消息体 |
| `@timestamp` | `false` | 时间戳（不展示为列） |

### Columns 生成

收集 `fields` 中 `displayDefault: true` 的条目，按定义顺序取 `fieldName` 组成 columns。

## <env-key>.json

```json
{
  "host": "<kibana-base-url>",
  "indices": { "<index-name>": "<描述>" }
}
```

- `indices` — key 是索引名称，value 是描述，UUID 从 API 获取

## UUID 获取

```bash
curl -s '${HOST}/api/saved_objects/_find?fields=title&fields=type&fields=typeMeta&per_page=10000&type=index-pattern' \
  -H 'kbn-version: 7.17.12' \
  -H 'content-type: application/json'
```

Response → `saved_objects[].{ id, attributes.title }`. 匹配 title (去掉 `*`) → 拿 `id` 作 UUID。

## 两段式流程

```
用户: "查看测试环境 game-openapi 最近 1h 的 error 或 warn 日志"
  → 先在技能目录跑 python3 scripts/load_kibana_context.py context
  → 返回 env/host/fields/defaultTimeRange/indexName->uuid mapping
  → LLM 用 原始请求 + context JSON 解析 Discover state
  → 若缺必要字段，用 context 里的选项问用户
  → 在技能目录跑 python3 scripts/load_kibana_context.py build-url --payload-json '<json>'
  → 最终 URL 直接使用 UUID
  → 输出 URL，再让用户选择是否打开
```

## `context` mode

```bash
python3 scripts/load_kibana_context.py context
python3 scripts/load_kibana_context.py context --env test
```

返回重点：
- environments
- fields
- defaultTimeRange
- per-env host
- per-env `indices` mapping (`indexName -> uuid`)

## LLM 参数解析职责

LLM 负责从原始自然语言里解析：
- `environment`
- `indexName`
- `indexUuid`
- `globalState`
- `appState.columns`
- `appState.sort`
- `appState.filters`
- `appState.query`

脚本不再解析自然语言，也不再预设 service / log-level / namespace / keyword 这些语义字段。

## `build-url` mode

```bash
python3 scripts/load_kibana_context.py build-url \
  --payload-json '{
    "host": "https://kibana.example.com",
    "indexName": "game-openapi",
    "indexUuid": "ef7b2550-d30f-11ef-9c9f-07d9d86326f2",
    "globalState": {
      "time": {"from": "now-1h", "to": "now"}
    },
    "appState": {
      "query": {
        "language": "kuery",
        "query": "message.level:\"error\" OR message.level:\"warn\""
      }
    }
  }'
```

必填 payload 字段：
- `host`
- `indexUuid`
- `globalState.time.from`
- `globalState.time.to`

可选 payload 字段：
- `indexName`
- `globalState.refreshInterval`
- `globalState.filters`
- `appState.columns`
- `appState.sort`
- `appState.filters`
- `appState.query`
- `appState.interval`

## Discover URL state model

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

## URL template

```
${HOST}/app/discover#/?_g=${RISON_GLOBAL_STATE}&_a=${RISON_APP_STATE}
```

## Filter template

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

`filters` 适合 exact/range/exists 等结构化约束。
`appState.query.query` 适合 OR / AND / 括号 / 文本搜索等 KQL 逻辑。
