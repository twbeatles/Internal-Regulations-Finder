# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from regfinder.app_types import AppConfig
from regfinder.persistence import ConfigManager, RecentFoldersStore, SearchLogStore


class PersistenceTest(unittest.TestCase):
    def test_config_manager_migrates_v1_schema(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "folder": "C:/docs",
                        "model": AppConfig.DEFAULT_MODEL,
                        "font": 15,
                        "hybrid": False,
                    },
                    f,
                    ensure_ascii=False,
                )

            with patch("regfinder.persistence.get_config_path", return_value=cfg_path):
                manager = ConfigManager()
                cfg = manager.load()

            self.assertEqual(cfg["schema_version"], AppConfig.CONFIG_SCHEMA_VERSION)
            self.assertEqual(cfg["folder"], "C:/docs")
            self.assertEqual(cfg["recent_folders"], ["C:/docs"])
            self.assertFalse(cfg["hybrid"])
            self.assertIn("filters", cfg)

    def test_recent_folders_store_dedup_and_order(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("regfinder.persistence.get_data_directory", return_value=td):
                store = RecentFoldersStore()
                store.add("C:/A")
                store.add("C:/B")
                store.add("C:/A")
                items = store.get()

            self.assertEqual(items[0], os.path.normpath("C:/A"))
            self.assertEqual(items[1], os.path.normpath("C:/B"))

    def test_search_log_summary(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("regfinder.persistence.get_data_directory", return_value=td):
                logs = SearchLogStore()
                logs.add("규정", 120, 3, True, "")
                logs.add("규정", 80, 1, True, "")
                logs.add("휴가", 200, 0, False, "SEARCH_FAIL")
                s = logs.summary()

            self.assertEqual(s["total"], 3)
            self.assertAlmostEqual(s["success_rate"], 66.7, places=1)
            self.assertGreaterEqual(s["avg_elapsed_ms"], 0)
            self.assertTrue(len(s["top_queries"]) >= 1)


if __name__ == "__main__":
    unittest.main()
