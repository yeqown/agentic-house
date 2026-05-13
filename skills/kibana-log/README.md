# kibana-log plugin

Claude Code plugin for constructing and opening Kibana Discover log search URLs from natural language queries. Index UUID is auto-discovered via Kibana API — no need to hardcode UUIDs.

## Quick start

```bash
export KIBANA_LOG_SKILL_HOME="$HOME/.agentic-house/kibana-log"

# Copy sample config and edit
cp -r /path/to/skills/kibana-log/config-sample/* "$KIBANA_LOG_SKILL_HOME/"

# Edit each file with your actual values
# 1. index.json  — environments, fields, defaults (usually no change needed)
# 2. test.json   — test env Kibana host, index names
# 3. prod.json   — prod env Kibana host, index names
```

### Config file layout

```
$KIBANA_LOG_SKILL_HOME/
├── index.json        # 通用配置
├── test.json         # 测试环境
├── prod.json         # 生产环境
└── pre.json          # 预发环境（可选）
```

### How UUID works

UUID is **not** stored in config. On each use:

1. Skill reads `host` from `<env>.json`
2. Calls Kibana API to list all index patterns
3. Matches index name (e.g. `example-portal`) to `title` field
4. Extracts `id` as UUID

This means adding new indices only requires editing `<env>.json` → `indices` — no UUID needed.

## Config reference

### index.json

| 字段 | 必填 | 说明 |
|---|---|---|
| `environments` | 是 | 环境列表，key 对应 `<env-key>.json` 文件名 |
| `fields` | 是 | ES 字段定义，每项含 `fieldName`、`description`、`displayDefault` |
| `defaultTimeRange` | 是 | 默认时间范围（`1h`, `30m`, `2h` 等） |

### \<env\>.json

| 字段 | 必填 | 说明 |
|---|---|---|
| `host` | 是 | Kibana base URL |
| `indices` | 是 | 索引名称列表，key 为索引名，value 为描述；不含 UUID |

## Behavior

- Request first runs `bin/load_kibana_context.py` to load runtime config, parse intent, and build a URL skeleton in one shot.
- Missing environment or business unit should prefer choice-based interaction from configured options, not free-form input.
- Final Kibana URL should be printed first, then the user chooses whether to open it.

Helper CLI entrypoint:
- `bin/load_kibana_context.py --query "查看测试环境用户平台 user-svc 日志"`
