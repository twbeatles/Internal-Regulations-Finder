# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import platform
import sys
import traceback
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

from .app_types import AppConfig, TaskResult
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


class RegulationQADiagnosticsMixin:
    def collect_diagnostics(self) -> Dict[str, Any]:
        try:
            frozen = bool(getattr(sys, "frozen", False))
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
            }

            try:
                torch = _import_module("torch")
                env["cuda_available"] = bool(torch.cuda.is_available())
            except Exception:
                env["cuda_available"] = None

            cache_summary: Dict[str, Any] = {"available": False}
            try:
                if self.model_id and self.current_folder and os.path.isdir(self.current_folder):
                    cache_dir = self.get_cache_dir_for_folder(self.current_folder)
                    cache_info_path = os.path.join(cache_dir, "cache_info.json")
                    if os.path.exists(cache_info_path):
                        with open(cache_info_path, "r", encoding="utf-8") as f:
                            ci = json.load(f) or {}
                        files = ci.get("files") if isinstance(ci, dict) else None
                        if isinstance(files, dict):
                            total_chunks = sum(int(v.get("chunks", 0) or 0) for v in files.values() if isinstance(v, dict))
                            cache_summary = {
                                "available": True,
                                "cache_dir": cache_dir,
                                "schema_version": ci.get("schema_version"),
                                "vector_id_mode": ci.get("vector_id_mode"),
                                "files": len(files),
                                "total_chunks": total_chunks,
                                "cache_info_mtime": os.path.getmtime(cache_info_path),
                            }
            except Exception as e:
                cache_summary = {"available": False, "error": str(e)}

            with self._diagnostics_lock:
                last_op = dict(self.last_op or {})

            return {"environment": env, "cache_summary": cache_summary, "last_op": last_op}
        except Exception:
            return {"error": traceback.format_exc()}

    def export_diagnostics_zip(self, path: str) -> TaskResult:
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
                        _try_add_file(zf, "cache/cache_info.json", os.path.join(cache_dir, "cache_info.json"))
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
        return self.cache_path

    def get_cache_dir_for_folder(self, folder: str) -> str:
        return self._get_cache_dir(folder)

    def get_cache_usage_bytes(self) -> int:
        total = 0
        if not os.path.exists(self.cache_path):
            return 0
        for dirpath, _, filenames in os.walk(self.cache_path):
            for name in filenames:
                fp = os.path.join(dirpath, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    continue
        return total

    def get_last_operation(self) -> Dict[str, Any]:
        with self._diagnostics_lock:
            return dict(self.last_op or {})

    def get_index_status(self, folder: Optional[str] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "cache_root": self.cache_path,
            "vector_loaded": bool(self.vector_store),
            "documents": len(self.documents),
            "file_infos": len(self.file_infos),
            "model_id": self.model_id or "",
        }
        target = folder or self.current_folder
        if not (target and os.path.isdir(target) and self.model_id):
            return data
        try:
            cache_dir = self._get_cache_dir(target)
            data["cache_dir"] = cache_dir
            ci_path = os.path.join(cache_dir, "cache_info.json")
            if os.path.exists(ci_path):
                with open(ci_path, "r", encoding="utf-8") as f:
                    ci = json.load(f) or {}
                files = ci.get("files", {}) if isinstance(ci, dict) else {}
                data["schema_version"] = ci.get("schema_version")
                data["cached_files"] = len(files) if isinstance(files, dict) else 0
                if isinstance(files, dict):
                    data["cached_chunks"] = sum(int((v or {}).get("chunks", 0) or 0) for v in files.values())
        except Exception as e:
            data["error"] = str(e)
        return data
