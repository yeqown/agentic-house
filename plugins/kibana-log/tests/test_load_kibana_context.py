from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bin" / "load_kibana_context.py"


class LoadKibanaContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self.temp_dir.name)
        (self.runtime_root / "index.json").write_text(
            textwrap.dedent(
                """
                {
                  "environments": {
                    "test": "example test environment",
                    "prod": "example production environment"
                  },
                  "fields": [
                    {
                      "fieldName": "containerName",
                      "description": "应用/容器名称，用于按服务过滤日志",
                      "displayDefault": true
                    },
                    {
                      "fieldName": "logLevel",
                      "description": "日志等级，如 ERROR/WARN/INFO/DEBUG",
                      "displayDefault": true
                    },
                    {
                      "fieldName": "message",
                      "description": "日志消息体，用于关键词搜索",
                      "displayDefault": true
                    },
                    {
                      "fieldName": "timestamp",
                      "description": "日志事件时间戳",
                      "displayDefault": false
                    }
                  ],
                  "defaultTimeRange": "1h"
                }
                """
            ).strip(),
            encoding="utf-8",
        )
        (self.runtime_root / "test.json").write_text(
            textwrap.dedent(
                """
                {
                  "host": "https://example-test-kibana.example.com/",
                  "indices": {
                    "nova-game-portal": "大厅日志索引",
                    "nova-payment": "支付系统日志索引"
                  }
                }
                """
            ).strip(),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_script(self, query: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["KIBANA_LOG_SKILL_HOME"] = str(self.runtime_root)
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--query", query, *extra_args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_outputs_context_bundle_for_complete_request(self) -> None:
        result = self.run_script("查看测试环境大厅 game-api 最近2小时 ERROR 日志")

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["intent"]["environment"], "test")
        self.assertEqual(payload["intent"]["indexName"], "nova-game-portal")
        self.assertEqual(payload["intent"]["service"], "game-api")
        self.assertEqual(payload["intent"]["logLevel"], "ERROR")
        self.assertEqual(payload["intent"]["timeRange"]["from"], "now-2h")
        self.assertEqual(payload["intent"]["timeRange"]["to"], "now")
        self.assertEqual(payload["missing"], [])
        self.assertIn("__INDEX_UUID__", payload["urlSkeleton"])
        self.assertIn("containerName", payload["urlSkeleton"])
        self.assertIn("game-api", payload["urlSkeleton"])

    def test_returns_index_candidates_when_request_lacks_business_unit(self) -> None:
        result = self.run_script("查看测试环境 game-api 日志")

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("indexName", payload["missing"])
        self.assertEqual(
            payload["candidates"]["indexName"],
            [
                {"value": "nova-game-portal", "label": "大厅日志索引"},
                {"value": "nova-payment", "label": "支付系统日志索引"},
            ],
        )

    def test_allows_overrides_to_fill_missing_values(self) -> None:
        result = self.run_script(
            "查看日志",
            "--env",
            "test",
            "--index",
            "nova-game-portal",
            "--service",
            "game-api",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["intent"]["environment"], "test")
        self.assertEqual(payload["intent"]["indexName"], "nova-game-portal")
        self.assertEqual(payload["intent"]["service"], "game-api")
        self.assertEqual(payload["missing"], [])


if __name__ == "__main__":
    unittest.main()
