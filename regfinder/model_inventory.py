# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

from .app_types import AppConfig, ModelDownloadState, ModelDownloadStateMap
from .runtime import (
    get_data_directory,
    get_model_cache_path,
    get_models_directory,
    is_model_downloaded,
    logger,
)


class ModelInventory:
    def __init__(self, inventory_path: str | None = None) -> None:
        self.inventory_path = inventory_path or os.path.join(get_data_directory(), "model_inventory.json")
        self._lock = threading.Lock()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.inventory_path):
            self._entries = {}
            return
        try:
            with open(self.inventory_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._entries = data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(f"모델 인벤토리 로드 실패: {self.inventory_path} - {exc}")
            self._entries = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.inventory_path) or ".", exist_ok=True)
            with open(self.inventory_path, "w", encoding="utf-8") as handle:
                json.dump(self._entries, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"모델 인벤토리 저장 실패: {self.inventory_path} - {exc}")

    def _dir_size(self, root: str) -> int:
        total = 0
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    continue
        return total

    def _path_mtime(self, path: str) -> float:
        try:
            return float(os.path.getmtime(path))
        except OSError:
            return 0.0

    def _to_public_state(self, entry: Dict[str, Any]) -> ModelDownloadState:
        return {
            "model_id": str(entry.get("model_id", "") or ""),
            "downloaded": bool(entry.get("downloaded", False)),
            "size_bytes": int(entry.get("size_bytes", 0) or 0),
            "cache_path": str(entry.get("cache_path", "") or ""),
        }

    def refresh(self, *, force: bool = False) -> ModelDownloadStateMap:
        with self._lock:
            models_dir = get_models_directory()
            next_entries: Dict[str, Dict[str, Any]] = {}
            for name, model_id in AppConfig.AVAILABLE_MODELS.items():
                cache_path = get_model_cache_path(model_id, models_dir=models_dir)
                downloaded = is_model_downloaded(model_id, models_dir=models_dir)
                path_mtime = self._path_mtime(cache_path) if os.path.isdir(cache_path) else 0.0
                cached = self._entries.get(name, {})
                should_rescan = (
                    force
                    or not isinstance(cached, dict)
                    or str(cached.get("model_id", "")) != model_id
                    or bool(cached.get("downloaded", False)) != downloaded
                    or float(cached.get("path_mtime", 0.0) or 0.0) != path_mtime
                )
                size_bytes = int(cached.get("size_bytes", 0) or 0)
                if should_rescan:
                    size_bytes = self._dir_size(cache_path) if downloaded and os.path.isdir(cache_path) else 0
                next_entries[name] = {
                    "model_id": model_id,
                    "downloaded": downloaded,
                    "size_bytes": size_bytes,
                    "cache_path": cache_path,
                    "path_mtime": path_mtime,
                }
            self._entries = next_entries
            self._save()
            return {name: self._to_public_state(entry) for name, entry in self._entries.items()}

    def snapshot(self) -> ModelDownloadStateMap:
        with self._lock:
            if not self._entries:
                return self.refresh(force=False)
            return {name: self._to_public_state(entry) for name, entry in self._entries.items()}
