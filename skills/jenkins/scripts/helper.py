#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def emit(payload: dict, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


def runtime_root() -> Path:
    value = os.environ.get("JENKINS_SKILL_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".agentic-house" / "jenkins-skill"


def git_output(*args: str) -> str:
    result = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def project_root_error() -> dict | None:
    repo_root = git_output("rev-parse", "--show-toplevel")
    if not repo_root:
        return {"ok": False, "error": "current directory is not a git repo root"}

    cwd = Path.cwd().resolve()
    root = Path(repo_root).resolve()
    if cwd != root:
        return {
            "ok": False,
            "error": f"run helper from project root: {root}",
            "cwd": str(cwd),
            "projectRoot": str(root),
        }
    return None


def load_config(root: Path) -> dict:
    config_path = root / "index.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def try_load_config(root: Path) -> tuple[dict | None, str | None]:
    config_path = root / "index.json"
    try:
        return load_config(root), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"index.json cannot be read: {e}"


# ---------------------------------------------------------------------------
# Internal helpers for subcommands that need context + Jenkins API access
# ---------------------------------------------------------------------------

_REMOTE_PATTERNS = [
    re.compile(r"^git@(?P<host>[^:]+):(?P<group>.+)/(?P<project>[^/]+?)\.git$"),
    re.compile(r"^https://(?P<host>[^/]+)/(?P<group>.+)/(?P<project>[^/]+?)\.git$"),
    re.compile(r"^ssh://git@(?P<host>[^:/]+)(?::\d+)?/(?P<group>.+)/(?P<project>[^/]+?)\.git$"),
]


def _resolve_context() -> dict:
    root_error = project_root_error()
    if root_error:
        return root_error
    if git_output("rev-parse", "--is-inside-work-tree") != "true":
        return {"ok": False, "error": "current directory is not a git repo"}

    remote = git_output("remote", "get-url", "origin")
    branch = git_output("branch", "--show-current")
    if not remote:
        return {"ok": False, "error": "origin remote is missing"}
    if not branch:
        return {"ok": False, "error": "current branch is empty"}

    for pattern in _REMOTE_PATTERNS:
        match = pattern.match(remote)
        if not match:
            continue
        group = match.group("group")
        project = match.group("project")
        return {
            "ok": True,
            "remote": remote,
            "branch": branch,
            "host": match.group("host"),
            "group": group,
            "project": project,
            "jobPath": f"{group}/{project}",
        }

    return {"ok": False, "error": "remote URL cannot be parsed into group/project", "remote": remote}


def _resolve_runtime_config() -> dict:
    root_error = project_root_error()
    if root_error:
        return root_error
    root = runtime_root()
    config_path = root / "index.json"
    if not config_path.exists():
        return {"ok": False, "error": "index.json is missing", "runtimeRoot": str(root)}

    config, error = try_load_config(root)
    if error:
        return {"ok": False, "error": error, "runtimeRoot": str(root)}

    host = str(config.get("host", "")).strip()
    auth = str(config.get("auth", "")).strip()
    if not host or not auth:
        return {"ok": False, "error": "index.json is missing host or auth", "runtimeRoot": str(root)}

    return {"ok": True, "host": host, "auth": auth, "runtimeRoot": str(root)}


def _resolve_metadata() -> dict:
    ctx = _resolve_context()
    if not ctx.get("ok"):
        return ctx

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return rt

    config, error = try_load_config(Path(rt["runtimeRoot"]))
    if error:
        return {"ok": False, "error": error, "runtimeRoot": rt["runtimeRoot"]}

    items = config.get("parameters")
    if not isinstance(items, list):
        return {
            "ok": False,
            "error": "index.json parameters must be a list",
            "runtimeRoot": rt["runtimeRoot"],
        }

    parameters: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        parameter = item.copy()
        parameter["name"] = name
        parameters.append(parameter)

    return {
        "ok": True,
        "remote": ctx["remote"],
        "branch": ctx["branch"],
        "host": rt["host"],
        "runtimeRoot": rt["runtimeRoot"],
        "jobPath": ctx["jobPath"],
        "parameters": parameters,
    }


def _parse_param_values(values: list[str]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for value in values:
        name, separator, parameter_value = value.partition("=")
        if not separator or not name:
            raise ValueError(f"invalid parameter assignment: {value}")
        parameters[name] = parameter_value
    return parameters


def _job_url_base(host: str, job_path: str) -> str:
    if not host.endswith("/"):
        host += "/"
    parts = job_path.strip("/").split("/")
    return host + "/".join(f"job/{p}" for p in parts) + "/"


def _jenkins_get(url: str, auth: str) -> dict:
    username, token = auth.split(":", 1)
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {credentials}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("Jenkins auth failed — check index.json auth credentials") from e
        if e.code == 404:
            raise RuntimeError(f"Jenkins resource not found: {url}") from e
        raise RuntimeError(f"Jenkins returned HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach Jenkins: {e.reason}") from e


def _jenkins_get_text(url: str, auth: str) -> str:
    username, token = auth.split(":", 1)
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {credentials}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Jenkins returned HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach Jenkins: {e.reason}") from e


def _normalize_parameter_type(raw_type: str) -> str:
    mapping = {
        "StringParameterDefinition": "string",
        "TextParameterDefinition": "text",
        "BooleanParameterDefinition": "boolean",
        "ChoiceParameterDefinition": "choice",
        "PasswordParameterDefinition": "password",
    }
    return mapping.get(raw_type, raw_type or "unknown")


def _extract_job_parameters(data: dict) -> list[dict]:
    parameters: list[dict] = []
    for prop in data.get("property", []):
        definitions = prop.get("parameterDefinitions", [])
        if not isinstance(definitions, list):
            continue
        for item in definitions:
            if not isinstance(item, dict):
                continue
            raw_type = str(item.get("type") or item.get("_class") or "").rsplit(".", 1)[-1]
            default_value = None
            default_parameter_value = item.get("defaultParameterValue")
            if isinstance(default_parameter_value, dict):
                default_value = default_parameter_value.get("value")
            elif "defaultValue" in item:
                default_value = item.get("defaultValue")
            choices = item.get("choices") or item.get("choicesAsString") or []
            if isinstance(choices, str):
                choices = [choice for choice in choices.splitlines() if choice]
            if not isinstance(choices, list):
                choices = []
            parameters.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "type": _normalize_parameter_type(raw_type),
                    "description": str(item.get("description", "")).strip(),
                    "default": default_value,
                    "availableValues": list(choices),
                }
            )
    return [parameter for parameter in parameters if parameter["name"]]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def command_metadata(_: argparse.Namespace) -> int:
    metadata = _resolve_metadata()
    return emit(metadata, 0 if metadata.get("ok") else 1)


def command_job_parameters(_: argparse.Namespace) -> int:
    ctx = _resolve_context()
    if not ctx.get("ok"):
        return emit(ctx, 1)

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return emit(rt, 1)

    base = _job_url_base(rt["host"], ctx["jobPath"])
    tree = "property[parameterDefinitions[name,type,_class,description,choices,choicesAsString,defaultValue,defaultParameterValue[value]]]"
    url = f"{base}api/json?tree={urllib.parse.quote(tree, safe='')}"

    try:
        data = _jenkins_get(url, rt["auth"])
    except RuntimeError as e:
        return emit({"ok": False, "error": str(e)}, 1)

    return emit({
        "ok": True,
        "jobPath": ctx["jobPath"],
        "url": base,
        "parameters": _extract_job_parameters(data),
    })


def command_trigger_command(args: argparse.Namespace) -> int:
    try:
        parameters = _parse_param_values(args.param)
    except ValueError as e:
        return emit({"ok": False, "error": str(e)}, 1)

    available_parameters = list(dict.fromkeys(args.available_param))
    available_parameter_names = set(available_parameters)
    for name in parameters:
        if name not in available_parameter_names:
            return emit(
                {
                    "ok": False,
                    "error": "unknown Jenkins parameter",
                    "parameter": name,
                    "availableParameters": available_parameters,
                },
                1,
            )

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return emit(rt, 1)

    root = Path(rt["runtimeRoot"])
    jar_path = root / "jenkins-cli.jar"
    if not jar_path.exists():
        return emit({"ok": False, "error": "jenkins-cli.jar is missing", "path": str(jar_path)}, 1)

    argv = [
        "java",
        "-jar",
        str(jar_path),
        "-s",
        rt["host"],
        "-auth",
        rt["auth"],
        "build",
        args.job_path,
    ]
    for name, value in parameters.items():
        argv.extend(["-p", f"{name}={value}"])

    return emit({"ok": True, "jobPath": args.job_path, "parameters": parameters, "argv": argv})


def command_last_build(args: argparse.Namespace) -> int:
    ctx = _resolve_context()
    if not ctx.get("ok"):
        return emit(ctx, 1)

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return emit(rt, 1)

    base = _job_url_base(rt["host"], ctx["jobPath"])
    tree = "lastBuild[number,url,result,building,duration,timestamp,actions[causes[userId,shortDescription],parameters[name,value]]]"
    url = f"{base}api/json?tree={urllib.parse.quote(tree, safe='')}"

    try:
        data = _jenkins_get(url, rt["auth"])
    except RuntimeError as e:
        return emit({"ok": False, "error": str(e)}, 1)

    build = data.get("lastBuild")
    if not build:
        return emit({"ok": False, "error": "no builds found for this job"}, 1)

    params: dict[str, str] = {}
    causes: list[dict] = []
    for action in build.get("actions", []):
        for param in action.get("parameters", []):
            if param.get("name") and param.get("value") is not None:
                params[param["name"]] = param["value"]
        for cause in action.get("causes", []):
            causes.append(cause)

    duration_ms = build.get("duration", 0)
    if build.get("building") and build.get("timestamp"):
        duration_ms = int(time.time() * 1000) - build["timestamp"]

    return emit({
        "ok": True,
        "branch": ctx["branch"],
        "jobPath": ctx["jobPath"],
        "buildNumber": build["number"],
        "url": build["url"],
        "result": build.get("result") or ("RUNNING" if build.get("building") else "UNKNOWN"),
        "building": build.get("building", False),
        "durationMs": duration_ms,
        "timestamp": build.get("timestamp"),
        "parameters": params,
        "causes": causes,
    })


def command_console_log(args: argparse.Namespace) -> int:
    ctx = _resolve_context()
    if not ctx.get("ok"):
        return emit(ctx, 1)

    rt = _resolve_runtime_config()
    if not rt.get("ok"):
        return emit(rt, 1)

    base = _job_url_base(rt["host"], ctx["jobPath"])
    build_number = args.build_number

    if not build_number:
        tree = "lastBuild[number]"
        url = f"{base}api/json?tree={urllib.parse.quote(tree, safe='')}"
        try:
            data = _jenkins_get(url, rt["auth"])
        except RuntimeError as e:
            return emit({"ok": False, "error": str(e)}, 1)
        build_number = data.get("lastBuild", {}).get("number")
        if not build_number:
            return emit({"ok": False, "error": "no builds found for this job"}, 1)

    console_url = f"{base}{build_number}/consoleText"
    try:
        text = _jenkins_get_text(console_url, rt["auth"])
    except RuntimeError as e:
        return emit({"ok": False, "error": str(e), "buildNumber": build_number}, 1)

    lines = text.splitlines()
    tail_count = args.tail or 80
    tailed = lines[-tail_count:] if len(lines) > tail_count else lines

    return emit({
        "ok": True,
        "buildNumber": build_number,
        "url": f"{base}{build_number}/",
        "totalLines": len(lines),
        "tailLines": len(tailed),
        "log": "\n".join(tailed),
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jenkins-skill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.set_defaults(handler=command_metadata)

    job_parameters_parser = subparsers.add_parser("job-parameters")
    job_parameters_parser.set_defaults(handler=command_job_parameters)

    trigger_command_parser = subparsers.add_parser("trigger-command")
    trigger_command_parser.add_argument("--job-path", required=True)
    trigger_command_parser.add_argument("--available-param", action="append", default=[])
    trigger_command_parser.add_argument("--param", action="append", default=[])
    trigger_command_parser.set_defaults(handler=command_trigger_command)

    last_build_parser = subparsers.add_parser("last-build")
    last_build_parser.set_defaults(handler=command_last_build)

    console_log_parser = subparsers.add_parser("console-log")
    console_log_parser.add_argument("--build-number", type=int, default=None)
    console_log_parser.add_argument("--tail", type=int, default=80)
    console_log_parser.set_defaults(handler=command_console_log)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
