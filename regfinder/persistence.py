# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from .app_types import AppConfig
from .runtime import get_config_path, get_data_directory, logger


def _safe_read_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"JSON 로드 실패: {path} - {e}")
        return default


def _safe_write_json(path: str, data: Any):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"JSON 저장 실패: {path} - {e}")


class ConfigManager:
    """설정 로드/저장 + 스키마 마이그레이션(v1 -> v2)."""

    def __init__(self):
        self.path = get_config_path()

    @staticmethod
    def defaults() -> Dict[str, Any]:
        return {
            "schema_version": AppConfig.CONFIG_SCHEMA_VERSION,
            "folder": "",
            "recent_folders": [],
            "model": AppConfig.DEFAULT_MODEL,
            "font": AppConfig.DEFAULT_FONT_SIZE,
            "hybrid": True,
            "recursive": False,
            "sort_by": "score_desc",
            "filters": {
                "extension": "",
                "filename": "",
                "path": "",
            },
        }

    def load(self) -> Dict[str, Any]:
        raw = _safe_read_json(self.path, None)
        defaults = self.defaults()
        if not isinstance(raw, dict):
            return defaults

        schema = int(raw.get("schema_version", 1) or 1)
        if schema <= 1:
            migrated = dict(defaults)
            migrated["folder"] = raw.get("folder", "") or ""
            if migrated["folder"]:
                migrated["recent_folders"] = [migrated["folder"]]
            migrated["model"] = raw.get("model", defaults["model"]) or defaults["model"]
            migrated["font"] = raw.get("font", defaults["font"]) or defaults["font"]
            migrated["hybrid"] = bool(raw.get("hybrid", defaults["hybrid"]))
            return migrated

        cfg = dict(defaults)
        cfg["folder"] = raw.get("folder", defaults["folder"]) or ""
        recents = raw.get("recent_folders", defaults["recent_folders"])
        if isinstance(recents, list):
            cfg["recent_folders"] = [str(x) for x in recents if isinstance(x, str) and x][:AppConfig.MAX_RECENT_FOLDERS]
        cfg["model"] = raw.get("model", defaults["model"]) or defaults["model"]
        cfg["font"] = int(raw.get("font", defaults["font"]) or defaults["font"])
        cfg["hybrid"] = bool(raw.get("hybrid", defaults["hybrid"]))
        cfg["recursive"] = bool(raw.get("recursive", defaults["recursive"]))
        cfg["sort_by"] = str(raw.get("sort_by", defaults["sort_by"]) or defaults["sort_by"])
        filters = raw.get("filters", {})
        if isinstance(filters, dict):
            cfg["filters"] = {
                "extension": str(filters.get("extension", "") or ""),
                "filename": str(filters.get("filename", "") or ""),
                "path": str(filters.get("path", "") or ""),
            }
        return cfg

    def save(self, cfg: Dict[str, Any]):
        payload = self.defaults()
        payload.update(cfg or {})
        payload["schema_version"] = AppConfig.CONFIG_SCHEMA_VERSION
        recents = payload.get("recent_folders", [])
        if not isinstance(recents, list):
            recents = []
        payload["recent_folders"] = [x for x in recents if isinstance(x, str) and x][:AppConfig.MAX_RECENT_FOLDERS]
        _safe_write_json(self.path, payload)


class JsonListStore:
    def __init__(self, filename: str, max_items: int):
        self.path = os.path.join(get_data_directory(), filename)
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        data = _safe_read_json(self.path, [])
        if isinstance(data, list):
            self.items = [x for x in data if isinstance(x, dict)][: self.max_items]
        else:
            self.items = []

    def _save(self):
        _safe_write_json(self.path, self.items[: self.max_items])

    def clear(self):
        self.items = []
        self._save()


class BookmarkStore(JsonListStore):
    def __init__(self):
        super().__init__(AppConfig.BOOKMARKS_FILE, AppConfig.MAX_BOOKMARKS)

    def add(self, query: str, item: Dict[str, Any]):
        source = str(item.get("source", "") or "")
        path = str(item.get("path", "") or "")
        content = str(item.get("content", "") or "")
        score = float(item.get("score", 0.0) or 0.0)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "query": query,
            "source": source,
            "path": path,
            "score": score,
            "content": content,
        }
        # 같은 파일+내용 앞부분 중복은 최신으로 갱신
        key = (entry["path"], entry["content"][:120])
        dedup: List[Dict[str, Any]] = []
        for old in self.items:
            old_key = (str(old.get("path", "")), str(old.get("content", ""))[:120])
            if old_key != key:
                dedup.append(old)
        self.items = [entry] + dedup
        self.items = self.items[: self.max_items]
        self._save()

    def remove(self, index: int):
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._save()


class RecentFoldersStore:
    def __init__(self):
        self.path = os.path.join(get_data_directory(), AppConfig.RECENTS_FILE)
        self.items: List[str] = []
        self._load()

    def _load(self):
        data = _safe_read_json(self.path, [])
        if isinstance(data, list):
            self.items = [str(x) for x in data if isinstance(x, str) and x][: AppConfig.MAX_RECENT_FOLDERS]
        else:
            self.items = []

    def _save(self):
        _safe_write_json(self.path, self.items[: AppConfig.MAX_RECENT_FOLDERS])

    def add(self, folder: str):
        folder = os.path.normpath(folder)
        self.items = [x for x in self.items if os.path.normpath(x) != folder]
        self.items.insert(0, folder)
        self.items = self.items[: AppConfig.MAX_RECENT_FOLDERS]
        self._save()

    def get(self) -> List[str]:
        return list(self.items)

    def clear(self):
        self.items = []
        self._save()


class SearchLogStore(JsonListStore):
    def __init__(self):
        super().__init__(AppConfig.SEARCH_LOG_FILE, AppConfig.MAX_SEARCH_LOGS)

    def add(self, query: str, elapsed_ms: int, result_count: int, success: bool, error_code: str = ""):
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "query": query,
            "elapsed_ms": int(max(0, elapsed_ms)),
            "result_count": int(max(0, result_count)),
            "success": bool(success),
            "error_code": str(error_code or ""),
        }
        self.items.insert(0, entry)
        self.items = self.items[: self.max_items]
        self._save()

    def summary(self) -> Dict[str, Any]:
        total = len(self.items)
        if total == 0:
            return {
                "total": 0,
                "success_rate": 0.0,
                "avg_elapsed_ms": 0,
                "avg_result_count": 0.0,
                "top_queries": [],
            }

        success_count = sum(1 for x in self.items if x.get("success"))
        elapsed_values = [int(x.get("elapsed_ms", 0) or 0) for x in self.items]
        avg_elapsed = int(sum(elapsed_values) / len(elapsed_values)) if elapsed_values else 0
        avg_result_count = sum(int(x.get("result_count", 0) or 0) for x in self.items) / total
        query_counter = Counter(str(x.get("query", "")).strip() for x in self.items if str(x.get("query", "")).strip())
        top_queries = [{"query": q, "count": c} for q, c in query_counter.most_common(5)]

        return {
            "total": total,
            "success_rate": round((success_count / total) * 100, 1),
            "avg_elapsed_ms": avg_elapsed,
            "avg_result_count": round(avg_result_count, 2),
            "top_queries": top_queries,
        }
