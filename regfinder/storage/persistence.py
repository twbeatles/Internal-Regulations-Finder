# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from ..core.runtime import get_config_path, get_data_directory, logger
from ..core.types import AppConfig


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


class _DebouncedJsonWriter:
    def __init__(self, path: str, delay_seconds: float) -> None:
        self.path = path
        self.delay_seconds = max(0.0, float(delay_seconds))
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._pending: Any = None

    def schedule(self, data: Any) -> None:
        if self.delay_seconds <= 0:
            _safe_write_json(self.path, data)
            return
        with self._lock:
            self._pending = data
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(self.delay_seconds, self.flush)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def flush(self) -> None:
        with self._lock:
            data = self._pending
            timer = self._timer
            self._pending = None
            self._timer = None
        if timer is not None:
            timer.cancel()
        if data is not None:
            _safe_write_json(self.path, data)


class ConfigManager:
    """설정 로드/저장 + 스키마 마이그레이션(v1 -> v4)."""

    def __init__(self):
        self.path = get_config_path()
        self._writer = _DebouncedJsonWriter(self.path, 0.2)

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
            "ocr_enabled": False,
            "ocr_mixed_pdf": False,
            "ocr_engine": "tesseract",
            "ocr_tesseract_cmd": "",
            "ocr_languages": "kor+eng",
            "keep_search_text": True,
            "sort_by": "score_desc",
            "filters": {
                "extension": "",
                "filename": "",
                "path": "",
            },
        }

    @staticmethod
    def _coerce_int(value: Any, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
        try:
            coerced = int(value)
        except Exception:
            coerced = default
        if minimum is not None:
            coerced = max(minimum, coerced)
        if maximum is not None:
            coerced = min(maximum, coerced)
        return coerced

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

    @staticmethod
    def _coerce_choice(value: Any, default: str, allowed: set[str]) -> str:
        text = str(value or "").strip()
        return text if text in allowed else default

    @staticmethod
    def _coerce_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value)

    def load(self) -> Dict[str, Any]:
        raw = _safe_read_json(self.path, None)
        defaults = self.defaults()
        if not isinstance(raw, dict):
            return defaults

        schema = self._coerce_int(raw.get("schema_version", 1), 1)
        if schema <= 1:
            migrated = dict(defaults)
            migrated["folder"] = self._coerce_str(raw.get("folder", ""), "")
            if migrated["folder"]:
                migrated["recent_folders"] = [migrated["folder"]]
            migrated["model"] = self._coerce_choice(
                raw.get("model", defaults["model"]),
                defaults["model"],
                set(AppConfig.AVAILABLE_MODELS.keys()),
            )
            migrated["font"] = self._coerce_int(
                raw.get("font", defaults["font"]),
                defaults["font"],
                minimum=AppConfig.MIN_FONT_SIZE,
                maximum=AppConfig.MAX_FONT_SIZE,
            )
            migrated["hybrid"] = self._coerce_bool(raw.get("hybrid", defaults["hybrid"]), defaults["hybrid"])
            migrated["ocr_enabled"] = self._coerce_bool(raw.get("ocr_enabled", defaults["ocr_enabled"]), defaults["ocr_enabled"])
            migrated["ocr_mixed_pdf"] = self._coerce_bool(raw.get("ocr_mixed_pdf", defaults["ocr_mixed_pdf"]), defaults["ocr_mixed_pdf"])
            migrated["keep_search_text"] = self._coerce_bool(raw.get("keep_search_text", defaults["keep_search_text"]), defaults["keep_search_text"])
            return migrated

        cfg = dict(defaults)
        cfg["folder"] = self._coerce_str(raw.get("folder", defaults["folder"]), defaults["folder"])
        recents = raw.get("recent_folders", defaults["recent_folders"])
        if isinstance(recents, list):
            cfg["recent_folders"] = [str(x) for x in recents if isinstance(x, str) and x][:AppConfig.MAX_RECENT_FOLDERS]
        cfg["model"] = self._coerce_choice(
            raw.get("model", defaults["model"]),
            defaults["model"],
            set(AppConfig.AVAILABLE_MODELS.keys()),
        )
        cfg["font"] = self._coerce_int(
            raw.get("font", defaults["font"]),
            defaults["font"],
            minimum=AppConfig.MIN_FONT_SIZE,
            maximum=AppConfig.MAX_FONT_SIZE,
        )
        cfg["hybrid"] = self._coerce_bool(raw.get("hybrid", defaults["hybrid"]), defaults["hybrid"])
        cfg["recursive"] = self._coerce_bool(raw.get("recursive", defaults["recursive"]), defaults["recursive"])
        cfg["ocr_enabled"] = self._coerce_bool(raw.get("ocr_enabled", defaults["ocr_enabled"]), defaults["ocr_enabled"])
        cfg["ocr_mixed_pdf"] = self._coerce_bool(raw.get("ocr_mixed_pdf", defaults["ocr_mixed_pdf"]), defaults["ocr_mixed_pdf"])
        cfg["ocr_engine"] = self._coerce_choice(
            raw.get("ocr_engine", defaults["ocr_engine"]),
            defaults["ocr_engine"],
            {"tesseract", "none"},
        )
        cfg["ocr_tesseract_cmd"] = self._coerce_str(raw.get("ocr_tesseract_cmd", defaults["ocr_tesseract_cmd"]), "")
        cfg["ocr_languages"] = self._coerce_str(raw.get("ocr_languages", defaults["ocr_languages"]), defaults["ocr_languages"]).strip() or defaults["ocr_languages"]
        cfg["keep_search_text"] = self._coerce_bool(raw.get("keep_search_text", defaults["keep_search_text"]), defaults["keep_search_text"])
        cfg["sort_by"] = self._coerce_choice(
            raw.get("sort_by", defaults["sort_by"]),
            defaults["sort_by"],
            {"score_desc", "filename_asc", "mtime_desc"},
        )
        filters = raw.get("filters", {})
        if isinstance(filters, dict):
            cfg["filters"] = {
                "extension": self._coerce_choice(
                    filters.get("extension", ""),
                    "",
                    set(AppConfig.SUPPORTED_EXTENSIONS) | {""},
                ),
                "filename": self._coerce_str(filters.get("filename", ""), ""),
                "path": self._coerce_str(filters.get("path", ""), ""),
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
        payload["model"] = self._coerce_choice(payload.get("model"), AppConfig.DEFAULT_MODEL, set(AppConfig.AVAILABLE_MODELS.keys()))
        payload["font"] = self._coerce_int(payload.get("font"), AppConfig.DEFAULT_FONT_SIZE, minimum=AppConfig.MIN_FONT_SIZE, maximum=AppConfig.MAX_FONT_SIZE)
        payload["hybrid"] = self._coerce_bool(payload.get("hybrid"), True)
        payload["recursive"] = self._coerce_bool(payload.get("recursive"), False)
        payload["ocr_enabled"] = self._coerce_bool(payload.get("ocr_enabled"), False)
        payload["ocr_mixed_pdf"] = self._coerce_bool(payload.get("ocr_mixed_pdf"), False)
        payload["ocr_engine"] = self._coerce_choice(payload.get("ocr_engine"), "tesseract", {"tesseract", "none"})
        payload["ocr_tesseract_cmd"] = self._coerce_str(payload.get("ocr_tesseract_cmd"), "")
        payload["ocr_languages"] = self._coerce_str(payload.get("ocr_languages"), "kor+eng").strip() or "kor+eng"
        payload["keep_search_text"] = self._coerce_bool(payload.get("keep_search_text"), True)
        payload["sort_by"] = self._coerce_choice(payload.get("sort_by"), "score_desc", {"score_desc", "filename_asc", "mtime_desc"})
        filters = payload.get("filters", {})
        if not isinstance(filters, dict):
            filters = {}
        payload["filters"] = {
            "extension": self._coerce_choice(filters.get("extension", ""), "", set(AppConfig.SUPPORTED_EXTENSIONS) | {""}),
            "filename": self._coerce_str(filters.get("filename", ""), ""),
            "path": self._coerce_str(filters.get("path", ""), ""),
        }
        self._writer.schedule(payload)

    def flush(self) -> None:
        self._writer.flush()


class JsonListStore:
    def __init__(self, filename: str, max_items: int, *, save_delay_seconds: float = 0.0):
        self.path = os.path.join(get_data_directory(), filename)
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []
        self._writer = _DebouncedJsonWriter(self.path, save_delay_seconds)
        self._load()

    def _load(self):
        data = _safe_read_json(self.path, [])
        if isinstance(data, list):
            self.items = [x for x in data if isinstance(x, dict)][: self.max_items]
        else:
            self.items = []

    def _save(self):
        self._writer.schedule(self.items[: self.max_items])

    def clear(self):
        self.items = []
        self._save()

    def flush(self):
        self._writer.flush()


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
            "page_start": item.get("page_start"),
            "page_end": item.get("page_end"),
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
        super().__init__(AppConfig.SEARCH_LOG_FILE, AppConfig.MAX_SEARCH_LOGS, save_delay_seconds=0.25)

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
