#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_REFRESH_INTERVAL = {"pause": True, "value": 0}
VALID_SORT_DIRECTIONS = {"asc", "desc"}


def runtime_root() -> Path:
    value = os.environ.get("KIBANA_LOG_SKILL_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".agentic-house" / "kibana-log"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def print_payload(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


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


def load_common_config(root: Path) -> tuple[Path, dict[str, object]]:
    index_path = root / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(index_path)
    return index_path, load_json(index_path)


def load_env_config(root: Path, environment: str) -> tuple[Path, dict[str, object]]:
    env_path = root / f"{environment}.json"
    if not env_path.exists():
        raise FileNotFoundError(env_path)
    return env_path, load_json(env_path)


def fetch_index_metadata(host: str) -> list[dict[str, str]]:
    request = urllib.request.Request(
        url=(
            f"{host.rstrip('/')}/api/saved_objects/_find"
            "?fields=title&fields=type&fields=typeMeta&per_page=10000&type=index-pattern"
        ),
        headers={
            "kbn-version": "7.17.12",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results: list[dict[str, str]] = []
    for item in payload.get("saved_objects", []):
        item_id = str(item.get("id", "")).strip()
        title = str(item.get("attributes", {}).get("title", "")).strip()
        if item_id and title:
            results.append({"id": item_id, "title": title})
    return results


def normalize_index_title(title: str) -> str:
    return title.rstrip("*").strip()


def match_configured_indices(
    configured_indices: dict[str, str], metadata: list[dict[str, str]]
) -> dict[str, str | None]:
    metadata_by_name = {normalize_index_title(item["title"]): item for item in metadata}
    matched: dict[str, str | None] = {}
    for index_name in configured_indices:
        metadata_item = metadata_by_name.get(index_name)
        matched[index_name] = metadata_item["id"] if metadata_item else None
    return matched


def select_default_columns(fields: list[dict[str, object]]) -> list[str]:
    columns: list[str] = []
    for item in fields:
        field_name = str(item.get("fieldName", "")).strip()
        if field_name and bool(item.get("displayDefault")):
            columns.append(field_name)
    return columns


def select_timestamp_field(fields: list[dict[str, object]]) -> str:
    for item in fields:
        field_name = str(item.get("fieldName", "")).strip()
        description = str(item.get("description", ""))
        if field_name == "@timestamp" or "时间戳" in description:
            return field_name
    return "@timestamp"


def rison_quote(value: str) -> str:
    escaped = value.replace("'", "!'")
    return f"'{escaped}'"


def rison_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_./~-]*", key):
        return key
    return rison_quote(key)


def rison_atom(value: object) -> str:
    if value is None:
        return "!n"
    if value is True:
        return "!t"
    if value is False:
        return "!f"
    if isinstance(value, str):
        if value == "":
            return "''"
        if value.startswith("@"):
            return rison_quote(value)
        if re.fullmatch(r"[A-Za-z_./~][A-Za-z0-9_./~]*", value):
            return value
        return rison_quote(value)
    return str(value)


def to_rison(value: object) -> str:
    if isinstance(value, dict):
        items = [f"{rison_key(key)}:{to_rison(item)}" for key, item in value.items()]
        return f"({','.join(items)})"
    if isinstance(value, list):
        items = ",".join(to_rison(item) for item in value)
        return f"!({items})"
    return rison_atom(value)


def load_payload_json(payload_json: str | None) -> dict[str, object] | None:
    if not payload_json:
        return None
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid payload JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload JSON must be an object")
    return payload


def build_default_app_state(common_config: dict[str, object], index_uuid: str) -> dict[str, object]:
    fields = common_config.get("fields", [])
    field_list = fields if isinstance(fields, list) else []
    timestamp_field = select_timestamp_field(field_list)
    return {
        "columns": select_default_columns(field_list),
        "filters": [],
        "index": index_uuid,
        "interval": "auto",
        "query": {"language": "kuery", "query": ""},
        "sort": [[timestamp_field, "desc"]],
    }


def build_default_global_state(default_time_range: str) -> dict[str, object]:
    return {
        "filters": [],
        "refreshInterval": dict(DEFAULT_REFRESH_INTERVAL),
        "time": {"from": f"now-{default_time_range}", "to": "now"},
    }


def merge_dict(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_filters(filters: object, index_uuid: str) -> list[dict[str, object]]:
    if filters is None:
        return []
    if not isinstance(filters, list):
        raise ValueError("filters must be an array")
    normalized: list[dict[str, object]] = []
    for item in filters:
        if not isinstance(item, dict):
            raise ValueError("each filter must be an object")
        normalized_filter = json.loads(json.dumps(item))
        meta = normalized_filter.get("meta")
        if isinstance(meta, dict):
            meta["index"] = index_uuid
        normalized.append(normalized_filter)
    return normalized


def normalize_columns(columns: object) -> list[str]:
    if columns is None:
        return []
    if not isinstance(columns, list):
        raise ValueError("appState.columns must be an array")
    normalized: list[str] = []
    for item in columns:
        value = str(item).strip()
        if not value:
            raise ValueError("appState.columns cannot contain empty values")
        normalized.append(value)
    return normalized


def normalize_sort(sort: object, default_sort: list[list[str]]) -> list[list[str]]:
    if sort is None:
        return default_sort
    if isinstance(sort, list) and len(sort) == 2 and all(not isinstance(item, list) for item in sort):
        sort = [sort]
    if not isinstance(sort, list):
        raise ValueError("appState.sort must be an array")
    normalized: list[list[str]] = []
    for item in sort:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("each appState.sort entry must be [field, direction]")
        field = str(item[0]).strip()
        direction = str(item[1]).strip().lower()
        if not field:
            raise ValueError("sort field cannot be empty")
        if direction not in VALID_SORT_DIRECTIONS:
            raise ValueError("sort direction must be asc or desc")
        normalized.append([field, direction])
    return normalized


def normalize_query(query: object) -> dict[str, str]:
    if query is None:
        return {"language": "kuery", "query": ""}
    if isinstance(query, str):
        return {"language": "kuery", "query": query}
    if not isinstance(query, dict):
        raise ValueError("appState.query must be an object or string")
    language = str(query.get("language", "kuery")).strip() or "kuery"
    query_text = str(query.get("query", ""))
    return {"language": language, "query": query_text}


def normalize_discover_state(payload: dict[str, object], common_config: dict[str, object]) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    host = str(payload.get("host", "")).strip()
    index_name = str(payload.get("indexName", "")).strip()
    index_uuid = str(payload.get("indexUuid", "")).strip()
    missing = [name for name, value in [("host", host), ("indexUuid", index_uuid)] if not value]
    if missing:
        raise ValueError(f"Missing required payload fields: {', '.join(missing)}")

    default_time_range = str(common_config.get("defaultTimeRange", "1h"))
    default_global_state = build_default_global_state(default_time_range)
    default_app_state = build_default_app_state(common_config, index_uuid)

    raw_global_state = payload.get("globalState", {})
    raw_app_state = payload.get("appState", {})
    if raw_global_state and not isinstance(raw_global_state, dict):
        raise ValueError("globalState must be an object")
    if raw_app_state and not isinstance(raw_app_state, dict):
        raise ValueError("appState must be an object")

    global_state = merge_dict(default_global_state, raw_global_state if isinstance(raw_global_state, dict) else {})
    app_state = merge_dict(default_app_state, raw_app_state if isinstance(raw_app_state, dict) else {})

    time_state = global_state.get("time")
    if not isinstance(time_state, dict):
        raise ValueError("globalState.time must be an object")
    from_time = str(time_state.get("from", "")).strip()
    to_time = str(time_state.get("to", "")).strip()
    if not from_time or not to_time:
        raise ValueError("globalState.time.from and globalState.time.to are required")

    app_state["index"] = index_uuid
    app_state["columns"] = normalize_columns(app_state.get("columns")) or default_app_state["columns"]
    app_state["filters"] = normalize_filters(app_state.get("filters"), index_uuid)
    global_state["filters"] = normalize_filters(global_state.get("filters"), index_uuid)
    app_state["query"] = normalize_query(app_state.get("query"))
    app_state["sort"] = normalize_sort(app_state.get("sort"), default_app_state["sort"])

    return host, {
        "indexName": index_name,
        "indexUuid": index_uuid,
    }, global_state, app_state


def build_discover_url(host: str, global_state: dict[str, object], app_state: dict[str, object]) -> str:
    return f"{host.rstrip('/')}/app/discover#/?_a={to_rison(app_state)}&_g={to_rison(global_state)}"


def build_context_payload(root: Path, requested_environment: str | None) -> dict[str, object]:
    index_path, common_config = load_common_config(root)
    environments = common_config.get("environments", {})
    fields = common_config.get("fields", [])
    default_time_range = str(common_config.get("defaultTimeRange", "1h"))
    if not isinstance(environments, dict):
        return error_payload("INVALID_INDEX_CONFIG", "index.json environments must be an object", runtimeRoot=str(root))

    target_environments: list[str]
    if requested_environment:
        if requested_environment not in environments:
            return error_payload(
                "UNKNOWN_ENVIRONMENT",
                f"Unknown environment: {requested_environment}",
                runtimeRoot=str(root),
                availableEnvironments=sorted(environments.keys()),
            )
        target_environments = [requested_environment]
    else:
        target_environments = list(environments.keys())

    config_files = [str(index_path)]
    environments_payload: dict[str, object] = {}
    for environment in target_environments:
        env_path, env_config = load_env_config(root, environment)
        config_files.append(str(env_path))
        host = str(env_config.get("host", "")).strip()
        if not host:
            return error_payload(
                "ENV_HOST_MISSING",
                f"{environment}.json is missing host",
                runtimeRoot=str(root),
                environment=environment,
            )
        indices = env_config.get("indices", {})
        if not isinstance(indices, dict):
            return error_payload(
                "INVALID_ENV_CONFIG",
                f"{environment}.json indices must be an object",
                runtimeRoot=str(root),
                environment=environment,
            )
        try:
            metadata = fetch_index_metadata(host)
        except FileNotFoundError:
            raise
        except urllib.error.HTTPError as exc:
            return error_payload(
                "INDEX_METADATA_FETCH_FAILED",
                f"Failed to fetch index metadata: HTTP {exc.code}",
                runtimeRoot=str(root),
                environment=environment,
                host=host,
            )
        except urllib.error.URLError as exc:
            return error_payload(
                "INDEX_METADATA_FETCH_FAILED",
                f"Failed to fetch index metadata: {exc.reason}",
                runtimeRoot=str(root),
                environment=environment,
                host=host,
            )

        matched_indices = match_configured_indices(indices, metadata)
        environments_payload[environment] = {
            "description": environments[environment],
            "host": host,
            "indices": matched_indices,
        }

    return {
        "ok": True,
        "runtime": {
            "runtimeRoot": str(root),
            "configFiles": config_files,
        },
        "config": {
            "fields": fields,
            "defaultTimeRange": default_time_range,
        },
        "environments": environments_payload,
    }


def build_url_payload(root: Path, args: argparse.Namespace) -> dict[str, object]:
    _, common_config = load_common_config(root)
    try:
        payload = load_payload_json(args.payload_json)
    except ValueError as exc:
        return error_payload("INVALID_PAYLOAD_JSON", str(exc))
    if payload is None:
        return error_payload("MISSING_REQUIRED_ARGUMENT", "Missing required arguments: payload_json", missing=["payload_json"])

    try:
        host, intent, global_state, app_state = normalize_discover_state(payload, common_config)
    except ValueError as exc:
        return error_payload("INVALID_DISCOVER_STATE", str(exc))

    url = build_discover_url(host, global_state, app_state)
    return {
        "ok": True,
        "intent": intent,
        "globalState": global_state,
        "appState": app_state,
        "url": url,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="load_kibana_context")
    subparsers = parser.add_subparsers(dest="mode")

    context_parser = subparsers.add_parser("context")
    context_parser.add_argument("--env")

    build_url_parser = subparsers.add_parser("build-url")
    build_url_parser.add_argument("--payload-json")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.mode:
        return print_payload(error_payload("MISSING_MODE", "Expected subcommand: context or build-url"))

    root = runtime_root()
    try:
        if args.mode == "context":
            return print_payload(build_context_payload(root, args.env))
        if args.mode == "build-url":
            return print_payload(build_url_payload(root, args))
    except FileNotFoundError as exc:
        missing_path = Path(exc.filename or str(exc))
        if missing_path.name == "index.json":
            return print_payload(
                error_payload("INDEX_JSON_MISSING", "index.json is missing", runtimeRoot=str(root))
            )
        return print_payload(
            error_payload(
                "ENV_CONFIG_MISSING",
                f"{missing_path.name} is missing",
                runtimeRoot=str(root),
                environment=missing_path.stem,
            )
        )

    return print_payload(error_payload("UNKNOWN_MODE", f"Unsupported mode: {args.mode}"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
