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

## \<env-key\>.json

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

## 字段验证

```bash
curl -s '${HOST}/api/index_patterns/_fields_for_wildcard?pattern=${NAME}*&meta_fields=_source&meta_fields=_id&meta_fields=_type&meta_fields=_index&meta_fields=_score' \
  -H 'kbn-version: 7.17.12' \
  -H 'content-type: application/json'
```

## 解析链

```
用户: "查看测试环境用户平台 user-svc 日志"
  → 先跑 load_kibana_context.py
  → 一次返回 env/host/indices/fields/service/timeRange/urlSkeleton
  → 若缺字段，基于 candidates 走选择题
  → 调 API 1 → 匹配 title "example-portal*" → UUID
  → 替换 urlSkeleton 中 __INDEX_UUID__ → 最终 URL
  → 输出 URL，再让用户选择是否打开
```

## Environment mapping

| 用户输入 | Key |
|---|---|
| 测试 / 测试环境 / test / staging | `test` |
| 生产 / 线上 / prod / production | `prod` |
| 预发 / pre / preprod | `pre` |

## Time range

| 用户输入 | from | to |
|---|---|---|
| 最近 2 小时 / last 2h | `now-2h` | `now` |
| 最近 30 分钟 / last 30m | `now-30m` | `now` |
| 今天 / today | `now/d` | `now` |
| 昨天 / yesterday | `now-1d/d` | `now/d` |
| 默认 (defaultTimeRange) | `now-${defaultTimeRange}` | `now` |

## Log level

| 用户输入 | Filter 值 |
|---|---|
| ERROR / 错误 | `ERROR` |
| WARN / 警告 | `WARN` |
| INFO / 信息 | `INFO` |
| DEBUG / 调试 | `DEBUG` |

## URL template

```
${HOST}/app/discover#/?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:'${FROM}',to:'${TO}'))&_a=(columns:!(${COLUMNS}),filters:${FILTERS_JSON},index:'${INDEX_UUID}',interval:auto,query:(language:kuery,query:'${QUERY}'),sort:!(!('${TIMESTAMP}',desc)))
```

## Filter template

```json
{
  "$state": { "store": "appState" },
  "meta": {
    "alias": null, "disabled": false,
    "index": "${INDEX_UUID}", "key": "${FIELD}",
    "negate": false, "params": { "query": "${VALUE}" },
    "type": "phrase"
  },
  "query": { "match_phrase": { "${FIELD}": "${VALUE}" } }
}
```

## Example inputs

### "查看测试环境用户平台 user-svc 的日志"
- env: `test`, unit: `用户平台` → `example-portal`
- API fetch UUID, service: `user-svc`
- columns: `message.level,message.msg,kubernetes.container_name`
- time: `now-1h` to `now`

### "搜索最近 2 小时，用户平台 gateway-svc 日志中包含 keyword 的日志"
- env: `test`, unit: `用户平台` → `example-portal`
- service: `gateway-svc`, keyword: `keyword`
- time: `now-2h` to `now`

### "查看线上 ERROR 级别 order-svc 日志"
- env: `prod`, unit: (must specify) → match description
- service: `order-svc`, log level: `ERROR`
- time: `now-1h` to `now`
