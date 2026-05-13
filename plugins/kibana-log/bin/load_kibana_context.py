#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote


UUID_PLACEHOLDER = "__INDEX_UUID__"


def runtime_root() -> Path:
    value = os.environ.get("KIBANA_LOG_SKILL_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".agentic-house" / "kibana-log"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def error_payload(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    payload.update(extra)
    return payload


def normalize_environment(query: str, override: str | None) -> str | None:
    if override:
        return override
    lowered = query.lower()
    if any(token in lowered for token in ["测试", "测试环境", "test", "staging", "int2", "int"]):
        return "test"
    if any(token in lowered for token in ["生产", "线上", "prod", "production"]):
        return "prod"
    if any(token in lowered for token in ["预发", "preprod", "pre"]):
        return "pre"
    return None


def normalize_log_level(query: str) -> str | None:
    upper = query.upper()
    if "ERROR" in upper or "错误" in query:
        return "ERROR"
    if "WARN" in upper or "警告" in query:
        return "WARN"
    if "INFO" in upper or "信息" in query:
        return "INFO"
    if "DEBUG" in upper or "调试" in query:
        return "DEBUG"
    return None


def normalize_time_range(query: str, default_time_range: str) -> dict[str, str]:
    match_hours = re.search(r"最近\s*(\d+)\s*(?:个)?小时", query)
    if match_hours:
        return {"from": f"now-{match_hours.group(1)}h", "to": "now"}

    match_hours_en = re.search(r"last\s*(\d+)h", query, re.IGNORECASE)
    if match_hours_en:
        return {"from": f"now-{match_hours_en.group(1)}h", "to": "now"}

    match_minutes = re.search(r"最近\s*(\d+)\s*分钟", query)
    if match_minutes:
        return {"from": f"now-{match_minutes.group(1)}m", "to": "now"}

    match_minutes_en = re.search(r"last\s*(\d+)m", query, re.IGNORECASE)
    if match_minutes_en:
        return {"from": f"now-{match_minutes_en.group(1)}m", "to": "now"}

    if "今天" in query or re.search(r"\btoday\b", query, re.IGNORECASE):
        return {"from": "now/d", "to": "now"}

    return {"from": f"now-{default_time_range}", "to": "now"}


def resolve_index(query: str, override: str | None, indices: dict[str, str]) -> tuple[str | None, str | None]:
    if override:
        description = indices.get(override, "")
        return override, description

    for name, description in indices.items():
        if name in query or description in query:
            return name, description
        normalized_description = description.replace("日志索引", "").replace("（", "").replace("）", "").strip()
        if normalized_description and normalized_description in query:
            return name, description
        for token in re.split(r"[\s()（）-]+", normalized_description):
            token = token.strip()
            if len(token) >= 2 and token in query:
                return name, description

    return None, None


def resolve_service(query: str, override: str | None) -> str | None:
    if override:
        return override

    service_before_logs = re.search(r"([A-Za-z][A-Za-z0-9_-]*)\s+(?:最近\s*\d+\s*(?:个)?(?:小时|分钟)\s+)?(?:ERROR|WARN|INFO|DEBUG)?\s*日志", query, re.IGNORECASE)
    if service_before_logs:
        return service_before_logs.group(1)

    match = re.search(r"([A-Za-z][A-Za-z0-9_-]*)\s*(?:的)?日志", query)
    if match:
        return match.group(1)

    return None


def select_fields(fields: list[dict[str, object]], keyword: str) -> tuple[str | None, str | None, str | None, list[str]]:
    service_field = None
    level_field = None
    message_field = None
    columns: list[str] = []

    for item in fields:
        field_name = str(item.get("fieldName", "")).strip()
        description = str(item.get("description", ""))
        display_default = bool(item.get("displayDefault"))
        if not field_name:
            continue
        if display_default:
            columns.append(field_name)
        if "容器" in description or "应用" in description:
            service_field = field_name
        if "日志等级" in description:
            level_field = field_name
        if "日志消息体" in description or "关键词" in description:
            message_field = field_name

    return service_field, level_field, message_field, columns


def build_filters(index_uuid: str, service_field: str | None, service: str | None, level_field: str | None, log_level: str | None) -> list[dict[str, object]]:
    filters: list[dict[str, object]] = []
    for field_name, value in [(service_field, service), (level_field, log_level)]:
        if not field_name or not value:
            continue
        filters.append(
            {
                "$state": {"store": "appState"},
                "meta": {
                    "alias": None,
                    "disabled": False,
                    "index": index_uuid,
                    "key": field_name,
                    "negate": False,
                    "params": {"query": value},
                    "type": "phrase",
                },
                "query": {"match_phrase": {field_name: value}},
            }
        )
    return filters


def build_url_skeleton(host: str, columns: list[str], time_range: dict[str, str], filters: list[dict[str, object]], message_field: str | None, keyword: str) -> str:
    query = "*"
    if keyword and message_field:
        query = f'{message_field}:"{keyword}"'

    columns_token = ",".join(columns)
    filters_token = quote(json.dumps(filters, ensure_ascii=False, separators=(",", ":")), safe="!()':,{}[]")
    query_token = quote(query, safe="*:\"-_")
    host_prefix = host.rstrip("/")
    return (
        f"{host_prefix}/app/discover#/?_g=(filters:!(),refreshInterval:(pause:!t,value:0),"
        f"time:(from:'{time_range['from']}',to:'{time_range['to']}'))"
        f"&_a=(columns:!({columns_token}),filters:{filters_token},index:'{UUID_PLACEHOLDER}',interval:auto,"
        f"query:(language:kuery,query:'{query_token}'),sort:!(!('timestamp',desc)))"
    )


def build_candidates(environments: dict[str, str], indices: dict[str, str], environment: str | None, index_name: str | None) -> dict[str, list[dict[str, str]]]:
    candidates = {
        "environment": [],
        "indexName": [],
        "service": [],
    }
    if environment is None:
        candidates["environment"] = [{"value": key, "label": value} for key, value in environments.items()]
    if index_name is None:
        candidates["indexName"] = [{"value": key, "label": value} for key, value in indices.items()]
    return candidates


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="load_kibana_context")
    parser.add_argument("--query", required=True)
    parser.add_argument("--env")
    parser.add_argument("--index")
    parser.add_argument("--service")
    args = parser.parse_args(argv)

    root = runtime_root()
    index_path = root / "index.json"
    if not index_path.exists():
        print(json.dumps(error_payload("INDEX_JSON_MISSING", "index.json is missing", runtimeRoot=str(root)), ensure_ascii=False))
        return 1

    index_config = load_json(index_path)
    environments = index_config.get("environments", {})
    fields = index_config.get("fields", [])
    default_time_range = str(index_config.get("defaultTimeRange", "1h"))

    environment = normalize_environment(args.query, args.env)
    if environment and environment not in environments:
        environment = None

    env_config: dict[str, object] = {}
    host = ""
    indices: dict[str, str] = {}
    env_path = None
    if environment:
        env_path = root / f"{environment}.json"
        if not env_path.exists():
            print(json.dumps(error_payload("ENV_CONFIG_MISSING", f"{environment}.json is missing", runtimeRoot=str(root), environment=environment), ensure_ascii=False))
            return 1
        env_config = load_json(env_path)
        host = str(env_config.get("host", "")).strip()
        indices = env_config.get("indices", {}) if isinstance(env_config.get("indices", {}), dict) else {}

    index_name, business_unit = resolve_index(args.query, args.index, indices)
    service = resolve_service(args.query, args.service)
    keyword = ""
    keyword_match = re.search(r"(?:包含|关键词|keyword|search)\s+([^\s]+)", args.query, re.IGNORECASE)
    if keyword_match:
        keyword = keyword_match.group(1)

    log_level = normalize_log_level(args.query)
    time_range = normalize_time_range(args.query, default_time_range)

    candidates = build_candidates(environments if isinstance(environments, dict) else {}, indices, environment, index_name)
    missing: list[str] = []
    if environment is None:
        missing.append("environment")
    if index_name is None:
        missing.append("indexName")
    if service is None:
        missing.append("service")

    service_field, level_field, message_field, columns = select_fields(fields if isinstance(fields, list) else [], keyword)
    filters = build_filters(UUID_PLACEHOLDER, service_field, service, level_field, log_level)
    url_skeleton = build_url_skeleton(host, columns, time_range, filters, message_field, keyword) if host else ""

    payload = {
        "ok": True,
        "runtime": {
            "runtimeRoot": str(root),
            "configFiles": [str(index_path)] + ([str(env_path)] if env_path else []),
        },
        "config": {
            "host": host,
            "environments": environments,
            "fields": fields,
            "indices": indices,
            "defaultTimeRange": default_time_range,
        },
        "intent": {
            "environment": environment,
            "businessUnit": business_unit,
            "indexName": index_name,
            "service": service,
            "keyword": keyword,
            "timeRange": time_range,
            "logLevel": log_level,
            "namespace": None,
        },
        "candidates": candidates,
        "missing": missing,
        "urlSkeleton": url_skeleton,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
