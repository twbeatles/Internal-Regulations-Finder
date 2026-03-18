# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import platform
import sys
import traceback
import zipfile
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from .app_types import AppConfig, TaskResult
from .model_inventory import ModelInventory
from .text_cache import TextCacheStore
from .runtime import (
    _import_module,
    get_config_path,
    get_data_directory,
    get_history_path,
    get_logs_directory,
    get_models_directory,
    get_op_logger,
    new_op_id,
)

if TYPE_CHECKING:
    from .qa_system import RegulationQASystem


def _as_qa(instance: object) -> RegulationQASystem:
    return cast("RegulationQASystem", instance)


class RegulationQADiagnosticsMixin:
    def collect_diagnostics(self) -> Dict[str, Any]:
        self = _as_qa(self)
        try:
            frozen = bool(getattr(sys, "frozen", False))
            model_inventory = ModelInventory().snapshot()
            env = {
                "app_name": AppConfig.APP_NAME,
                "app_version": AppConfig.APP_VERSION,
                "python": sys.version,
                "platform": platform.platform(),
                "frozen": frozen,
                "data_dir": get_data_directory(),
                "models_dir": get_models_directory(),
                "logs_dir": get_logs_directory(),
                "cache_root": self.cache_path,
                "current_folder": self.current_folder,
                "vector_id_mode": self._vector_id_mode,
                "cache_schema_version": getattr(self, "CACHE_SCHEMA_VERSION", None),
                "text_cache_path": self.current_text_cache_path,
                "vector_cache_dir": self.current_vector_cache_dir,
                "vector_ready": bool(self.vector_store),
                "bm25_ready": self.bm25 is not None and bool(self.documents),
                "search_mode": self._index_search_mode,
                "memory_warning": bool(getattr(self, "_memory_warning", False)),
            }

            try:
                torch = _import_module("torch")
                env["cuda_available"] = bool(torch.cuda.is_available())
            except Exception:
                env["cuda_available"] = None

            cache_summary: Dict[str, Any] = {"available": False}
            try:
                if self.model_id and self.current_folder and os.path.isdir(self.current_folder):
                    text_cache = TextCacheStore(self._get_text_cache_path(self.current_folder), self.CACHE_SCHEMA_VERSION)
                    text_snapshot = text_cache.snapshot()
                    vector_cache_dir = self.get_cache_dir_for_folder(self.current_folder)
                    vector_meta_path = os.path.join(vector_cache_dir, "vector_meta.json")
                    vector_meta = {}
                    if os.path.exists(vector_meta_path):
                        with open(vector_meta_path, "r", encoding="utf-8") as f:
                            vector_meta = json.load(f) or {}
                    cache_summary = {
                        "available": True,
                        "text_cache_path": text_snapshot.sqlite_path,
                        "text_cache_revision": text_snapshot.revision,
                        "vector_cache_dir": vector_cache_dir,
                        "schema_version": text_snapshot.schema_version,
                        "vector_id_mode": vector_meta.get("vector_id_mode"),
                        "files": text_snapshot.cached_files,
                        "total_chunks": text_snapshot.cached_chunks,
                        "updated_at": text_snapshot.updated_at,
                    }
            except Exception as e:
                cache_summary = {"available": False, "error": str(e)}

            with self._diagnostics_lock:
                last_op = dict(self.last_op or {})

            return {
                "environment": env,
                "cache_summary": cache_summary,
                "last_op": last_op,
                "last_search_stats": {
                    "elapsed_ms": self.last_search_stats.elapsed_ms,
                    "vector_fetch_k": self.last_search_stats.vector_fetch_k,
                    "bm25_candidates": self.last_search_stats.bm25_candidates,
                    "filtered_out": self.last_search_stats.filtered_out,
                    "result_count": self.last_search_stats.result_count,
                    "query_len": self.last_search_stats.query_len,
                    "search_mode": self.last_search_stats.search_mode,
                    "vector_ready": self.last_search_stats.vector_ready,
                    "filters": dict(self.last_search_stats.filters),
                },
                "model_inventory": model_inventory,
            }
        except Exception:
            return {"error": traceback.format_exc()}

    def export_diagnostics_zip(self, path: str) -> TaskResult:
        self = _as_qa(self)
        op_id = new_op_id("DIAG")
        log = get_op_logger(op_id)
        started = datetime.now()
        manifest: Dict[str, Any] = {"op_id": op_id, "created_at": datetime.now().isoformat(timespec="seconds"), "items": []}

        def _try_add_file(zf: zipfile.ZipFile, arcname: str, src: str):
            item = {"type": "file", "arcname": arcname, "src": src, "ok": False}
            try:
                if os.path.exists(src) and os.path.isfile(src):
                    zf.write(src, arcname=arcname)
                    item["ok"] = True
                else:
                    item["error"] = "not_found"
            except Exception as e:
                item["error"] = str(e)
            manifest["items"].append(item)

        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                diag = self.collect_diagnostics()
                zf.writestr("environment.json", json.dumps(diag.get("environment", {}), ensure_ascii=False, indent=2))
                zf.writestr("cache_summary.json", json.dumps(diag.get("cache_summary", {}), ensure_ascii=False, indent=2))
                zf.writestr("last_op.json", json.dumps(diag.get("last_op", {}), ensure_ascii=False, indent=2))

                _try_add_file(zf, "config.json", get_config_path())
                _try_add_file(zf, "search_history.json", get_history_path())

                logs_dir = get_logs_directory()
                if os.path.isdir(logs_dir):
                    for name in os.listdir(logs_dir):
                        if name.startswith("app.log"):
                            _try_add_file(zf, f"logs/{name}", os.path.join(logs_dir, name))

                try:
                    if self.model_id and self.current_folder and os.path.isdir(self.current_folder):
                        cache_dir = self._get_cache_dir(self.current_folder)
                        _try_add_file(zf, "cache/vector_meta.json", os.path.join(cache_dir, "vector_meta.json"))
                        _try_add_file(zf, "cache/text_cache.sqlite", self._get_text_cache_path(self.current_folder))
                except Exception as e:
                    manifest["items"].append({"type": "cache", "ok": False, "error": str(e)})

                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

            elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
            log.info(f"진단 번들 생성 완료: {path} ({elapsed_ms}ms)")
            return TaskResult(True, "진단 번들 생성 완료", {"path": path}, op_id=op_id)
        except Exception as e:
            log.exception("진단 번들 생성 실패")
            return TaskResult(False, f"진단 번들 생성 실패: {e}", op_id=op_id, error_code="DIAG_EXPORT_FAIL", debug=traceback.format_exc())

    def get_cache_root(self) -> str:
        self = _as_qa(self)
        return self.cache_path

    def get_cache_dir_for_folder(self, folder: str) -> str:
        self = _as_qa(self)
        return self._get_cache_dir(folder)

    def get_cache_usage_bytes(self) -> int:
        self = _as_qa(self)
        return int(self._cache_usage_bytes_snapshot)

    def refresh_cache_usage_bytes(self) -> int:
        self = _as_qa(self)
        total = 0
        if not os.path.exists(self.cache_path):
            self._cache_usage_bytes_snapshot = 0
            return 0
        for dirpath, _, filenames in os.walk(self.cache_path):
            for name in filenames:
                fp = os.path.join(dirpath, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    continue
        self._cache_usage_bytes_snapshot = total
        return total

    def get_last_operation(self) -> Dict[str, Any]:
        self = _as_qa(self)
        with self._diagnostics_lock:
            return dict(self.last_op or {})

    def get_index_status(self, folder: Optional[str] = None) -> Dict[str, Any]:
        self = _as_qa(self)
        data: Dict[str, Any] = {
            "cache_root": self.cache_path,
            "vector_loaded": bool(self.vector_store),
            "vector_ready": bool(self.vector_store),
            "bm25_ready": self.bm25 is not None and bool(self.documents),
            "search_mode": self._index_search_mode,
            "memory_warning": bool(getattr(self, "_memory_warning", False)),
            "documents": len(self.documents),
            "file_infos": len(self.file_infos),
            "model_id": self.model_id or "",
            "text_cache_revision": self.text_cache_revision,
        }
        target = folder or self.current_folder
        if not (target and os.path.isdir(target) and self.model_id):
            return data
        try:
            cache_dir = self._get_cache_dir(target)
            text_cache = TextCacheStore(self._get_text_cache_path(target), self.CACHE_SCHEMA_VERSION)
            snapshot = text_cache.snapshot()
            data["cache_dir"] = cache_dir
            data["text_cache_path"] = snapshot.sqlite_path
            data["schema_version"] = snapshot.schema_version
            data["cached_files"] = snapshot.cached_files
            data["cached_chunks"] = snapshot.cached_chunks
            data["text_cache_revision"] = snapshot.revision
            vector_meta_path = os.path.join(cache_dir, "vector_meta.json")
            if os.path.exists(vector_meta_path):
                with open(vector_meta_path, "r", encoding="utf-8") as f:
                    vector_meta = json.load(f) or {}
                data["vector_meta_revision"] = vector_meta.get("text_cache_revision")
                data["vector_id_mode"] = vector_meta.get("vector_id_mode")
        except Exception as e:
            data["error"] = str(e)
        return data
