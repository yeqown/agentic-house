# Kibana Log Skill Reference

## 目录

- Config file layout
- index.json schema
- Per-environment config (`<env-key>.json`)
- UUID resolution (Kibana API)
- `load_kibana_context.py` commands
- Discover URL state model
- Filter object template
- Query vs filters

## Config file layout

```
$HOME/.agentic-house/kibana-log/
├── index.json        # Common config (environments, fields, defaults)
├── test.json         # Per-env config (host, indices)
├── prod.json
└── pre.json          # Optional
```

Sample config: `skills/kibana/config-sample/`

## index.json schema

```json
{
  "environments": { "<env-key>": "<description>" },
  "fields": [
    {
      "fieldName": "<ES field name>",
      "description": "<meaning>",
      "displayDefault": true
    }
  ],
  "defaultTimeRange": "<e.g. 1h>"
}
```

| Field | Description |
| --- | --- |
| `environments` | Key maps to `<env-key>.json` filename, value is description |
| `fields[].fieldName` | Actual ES field name |
| `fields[].description` | Field meaning for LLM mapping |
| `fields[].displayDefault` | `true` → show as Discover column by default |
| `defaultTimeRange` | Default time range (e.g. `1h`, `30m`, `2h`) |

### Columns derivation

Collect all `fields` entries where `displayDefault: true`, take `fieldName` values in definition order.

## Per-environment config (`<env-key>.json`)

```json
{
  "host": "https://kibana.example.net/",
  "indices": {
    "example-portal": "Portal logs index",
    "example-payment": "Payment system logs index"
  }
}
```

| Field | Description |
| --- | --- |
| `host` | Kibana base URL |
| `indices` | Key = index name, value = description. UUID resolved dynamically via API |

## UUID resolution (Kibana API)

```bash
curl -s '${HOST}/api/saved_objects/_find?fields=title&fields=type&fields=typeMeta&per_page=10000&type=index-pattern' \
  -H 'kbn-version: 7.17.12' \
  -H 'content-type: application/json'
```

Response: `saved_objects[].{ id, attributes.title }`. Match `title` (strip trailing `*`) → use `id` as UUID.

## `load_kibana_context.py` commands

### `context` mode

```bash
python3 scripts/load_kibana_context.py context          # All environments
python3 scripts/load_kibana_context.py context --env test  # Single environment
```

Returns: `environments`, `fields`, `defaultTimeRange`, per-env `host`, `indexName -> uuid` mapping.

### `build-url` mode

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

Required payload fields: `host`, `indexUuid`, `globalState.time.from`, `globalState.time.to`

Optional payload fields: `indexName`, `globalState.refreshInterval`, `globalState.filters`, `appState.columns`, `appState.sort`, `appState.filters`, `appState.query`, `appState.interval`

## Discover URL state model

```
${HOST}/app/discover#/?_g=${RISON_GLOBAL_STATE}&_a=${RISON_APP_STATE}
```

### `_g` (global state)

- `time` — `{ "from": "now-1h", "to": "now" }`
- `refreshInterval`
- global `filters`

### `_a` (app state)

- `index` — UUID of the index pattern
- `columns` — field names for display
- `sort` — sort field and order
- app `filters`
- `query` — `{ "language": "kuery", "query": "..." }`

## Filter object template

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

`meta.index` must match the top-level `index` UUID.

## Query vs filters

- `filters` — structured constraints: exact match, range, exists
- `appState.query.query` — KQL logic: OR, AND, parentheses, text search
