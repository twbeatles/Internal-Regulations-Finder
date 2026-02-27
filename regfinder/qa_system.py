# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import threading
import traceback
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .app_types import AppConfig, FileInfo, FileStatus, TaskResult
from .bm25 import BM25Light
from .document_extractor import BaseOCREngine, DocumentExtractor, NoOpOCREngine
from .file_utils import FileUtils
from .runtime import (
    _import_attr,
    _import_module,
    get_config_path,
    get_data_directory,
    get_history_path,
    get_logs_directory,
    get_models_directory,
    get_op_logger,
    logger,
    new_op_id,
)

class RegulationQASystem:
    def __init__(self):
        self.vector_store = None
        self.embedding_model = None
        self.model_id = None
        self.extractor = DocumentExtractor()
        self.cache_path = os.path.join(tempfile.gettempdir(), "reg_qa_v90")
        self.bm25 = None
        self.documents: List[str] = []
        self.doc_meta: List[Dict] = []
        self.doc_ids: List[str] = []
        self._vector_id_mode: str = "auto"  # "doc_id" | "auto"
        self.file_infos: Dict[str, FileInfo] = {}
        self.current_folder = ""
        self._lock = threading.Lock()
        self.last_op: Dict[str, Any] = {}
        self._diagnostics_lock = threading.Lock()

    def reset_runtime_state(self, reset_model: bool = False):
        """세션 인덱스/메모리 상태 초기화."""
        self.vector_store = None
        self._vector_id_mode = "auto"
        self.documents.clear()
        self.doc_meta.clear()
        self.doc_ids.clear()
        self.file_infos.clear()
        self.current_folder = ""
        if self.bm25:
            self.bm25.clear()
        self.bm25 = None
        if reset_model:
            self.embedding_model = None
            self.model_id = None

    def collect_diagnostics(self) -> Dict[str, Any]:
        """문제 재현/분석을 위한 최소 진단 정보(문서 원문/청크 내용은 포함하지 않음)."""
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

            # GPU 여부는 torch import 비용이 크므로 best-effort로만 확인
            try:
                torch = _import_module("torch")
                env["cuda_available"] = bool(torch.cuda.is_available())
            except Exception:
                env["cuda_available"] = None

            # 캐시 요약(가능하면 cache_info.json 기반으로만)
            cache_summary: Dict[str, Any] = {"available": False}
            try:
                if self.model_id and self.current_folder and os.path.isdir(self.current_folder):
                    cache_dir = self._get_cache_dir(self.current_folder)
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
        """진단 번들(zip) 내보내기. 누락 항목이 있어도 가능한 범위에서 생성."""
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
                # environment.json + cache_summary.json + last_op.json
                diag = self.collect_diagnostics()
                zf.writestr("environment.json", json.dumps(diag.get("environment", {}), ensure_ascii=False, indent=2))
                zf.writestr("cache_summary.json", json.dumps(diag.get("cache_summary", {}), ensure_ascii=False, indent=2))
                zf.writestr("last_op.json", json.dumps(diag.get("last_op", {}), ensure_ascii=False, indent=2))

                # config/history
                _try_add_file(zf, "config.json", get_config_path())
                _try_add_file(zf, "search_history.json", get_history_path())

                # logs (best-effort)
                logs_dir = get_logs_directory()
                if os.path.isdir(logs_dir):
                    for name in os.listdir(logs_dir):
                        if name.startswith("app.log"):
                            _try_add_file(zf, f"logs/{name}", os.path.join(logs_dir, name))

                # cache_info.json only (no docs/index to avoid large+unsafe content)
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

    def load_model(self, model_name: str, progress_cb=None, op_id: Optional[str] = None) -> TaskResult:
        op_id = op_id or new_op_id("MODEL")
        log = get_op_logger(op_id)
        model_id = AppConfig.AVAILABLE_MODELS.get(model_name, AppConfig.AVAILABLE_MODELS[AppConfig.DEFAULT_MODEL])
        started = datetime.now()
        try:
            if progress_cb: progress_cb("라이브러리 로드 중...")
            torch = _import_module("torch")
            HuggingFaceEmbeddings = _import_attr("langchain_huggingface", "HuggingFaceEmbeddings")
            if progress_cb: progress_cb("모델 로딩 중...")
            cache_dir = get_models_directory()
            os.makedirs(cache_dir, exist_ok=True)
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            log.info(f"모델 로드 시작: {model_name} ({device})")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=model_id, cache_folder=cache_dir,
                model_kwargs={'device': device}, encode_kwargs={'normalize_embeddings': True}
            )
            self.model_id = model_id
            gc.collect()
            if device == 'cuda': torch.cuda.empty_cache()
            elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
            log.info(f"모델 로드 완료: {model_name} ({device}) ({elapsed_ms}ms)")
            with self._diagnostics_lock:
                self.last_op = {
                    "op_id": op_id,
                    "kind": "load_model",
                    "model_name": model_name,
                    "device": device,
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "ts": datetime.now().isoformat(timespec="seconds"),
                }
            return TaskResult(True, f"모델 로드 완료 ({device})", op_id=op_id)
        except Exception as e:
            log.exception(f"모델 로드 실패: {e}")
            with self._diagnostics_lock:
                self.last_op = {
                    "op_id": op_id,
                    "kind": "load_model",
                    "model_name": model_name,
                    "success": False,
                    "elapsed_ms": int((datetime.now() - started).total_seconds() * 1000),
                    "ts": datetime.now().isoformat(timespec="seconds"),
                }
            return TaskResult(
                False,
                f"모델 로드 실패: {e}",
                op_id=op_id,
                error_code="MODEL_LOAD_FAIL",
                debug=traceback.format_exc(),
            )
    
    def _get_cache_dir(self, folder: str) -> str:
        if not self.model_id:
            raise ValueError("모델이 로드되지 않았습니다")
        folder = os.path.normpath(os.path.abspath(folder))
        h1 = hashlib.md5(self.model_id.encode()).hexdigest()[:6]
        h2 = hashlib.md5(folder.encode()).hexdigest()[:6]
        return os.path.join(self.cache_path, f"{h2}_{h1}")
    
    def process_documents(
        self,
        folder: str,
        files: List[str],
        progress_cb,
        cancel_check=None,
        op_id: Optional[str] = None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_options: Optional[Dict[str, Any]] = None,
    ) -> TaskResult:
        if not self.embedding_model:
            return TaskResult(False, "모델이 로드되지 않았습니다", op_id=op_id or "", error_code="MODEL_NOT_LOADED")
        folder = os.path.normpath(os.path.abspath(folder))
        op_id = op_id or new_op_id("DOCS")
        log = get_op_logger(op_id)
        started = datetime.now()
        log.info(f"문서 처리 시작: folder={folder} files={len(files)}")
        ocr_engine = self._resolve_ocr_engine(ocr_options)
        with self._lock:
            result = self._process_internal(
                folder,
                files,
                progress_cb,
                cancel_check,
                pdf_passwords=pdf_passwords,
                ocr_engine=ocr_engine,
            )
        elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        result.op_id = result.op_id or op_id
        with self._diagnostics_lock:
            self.last_op = {
                "op_id": op_id,
                "kind": "process_documents",
                "folder": folder,
                "files": len(files),
                "success": bool(result.success),
                "elapsed_ms": elapsed_ms,
                "failed_items_count": len(result.failed_items or []),
                "ts": datetime.now().isoformat(timespec="seconds"),
            }
        log.info(f"문서 처리 완료: success={result.success} elapsed={elapsed_ms}ms failed={len(result.failed_items or [])}")
        # 문서/인덱스가 바뀌었으니 검색 캐시 무효화(추후 LRU 캐시 추가 시 대비)
        return result
    
    # 캐시 스키마
    CACHE_SCHEMA_VERSION = 2

    def _file_key(self, folder: str, fp: str) -> str:
        """folder 기준 상대경로(슬래시 통일)로 캐시 키 생성."""
        folder = os.path.normpath(os.path.abspath(folder))
        fp = os.path.normpath(os.path.abspath(fp))
        try:
            rel = os.path.relpath(fp, folder)
        except Exception:
            rel = os.path.basename(fp)
        return rel.replace("\\", "/")

    def _empty_cache_info(self) -> Dict[str, Any]:
        return {"schema_version": self.CACHE_SCHEMA_VERSION, "vector_id_mode": self._vector_id_mode, "files": {}}

    def _is_cache_compatible(self, cache_info: Dict) -> bool:
        return (
            isinstance(cache_info, dict)
            and cache_info.get("schema_version") == self.CACHE_SCHEMA_VERSION
            and isinstance(cache_info.get("files"), dict)
            and isinstance(cache_info.get("vector_id_mode"), str)
        )

    def _resolve_ocr_engine(self, ocr_options: Optional[Dict[str, Any]]) -> Optional[BaseOCREngine]:
        if isinstance(ocr_options, dict):
            if ocr_options.get("enabled") is False:
                return None
            engine = ocr_options.get("engine")
            if engine and hasattr(engine, "extract_pdf_images"):
                return engine
        return NoOpOCREngine()

    def _process_internal(
        self,
        folder,
        files,
        progress_cb,
        cancel_check=None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> TaskResult:
        self.current_folder = folder
        cache_dir = self._get_cache_dir(folder)
        self.file_infos.clear()

        # FileInfo 초기화
        for fp in files:
            meta = FileUtils.get_metadata(fp)
            self.file_infos[fp] = FileInfo(
                fp,
                os.path.basename(fp),
                os.path.splitext(fp)[1].lower(),
                meta["size"] if meta else 0,
            )

        progress_cb(10, "캐시 확인...")
        cache_info = self._load_cache_info(cache_dir)
        if not self._is_cache_compatible(cache_info):
            # 구 스키마/손상 캐시: 안전하게 폐기 후 재생성
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir, ignore_errors=True)
            cache_info = self._empty_cache_info()

        current: Dict[str, Dict[str, Any]] = {}
        for fp in files:
            key = self._file_key(folder, fp)
            if key in current:
                # 중복 상대경로는 정상 케이스가 아니므로, 뒤 항목은 무시(캐시 오염 방지)
                logger.warning(f"중복 파일 키 감지, 무시됨: {key} ({fp})")
                continue
            current[key] = {"path": fp, "meta": FileUtils.get_metadata(fp)}

        cached_files: Dict[str, Dict] = cache_info.get("files", {})

        cur_keys = set(current.keys())
        cache_keys = set(cached_files.keys())
        deleted_keys = cache_keys - cur_keys
        added_keys = cur_keys - cache_keys
        modified_keys = set()
        unchanged_keys = set()

        for k in (cur_keys & cache_keys):
            meta = current[k].get("meta") or {}
            cm = cached_files.get(k) or {}
            if meta and cm.get("size") == meta.get("size") and cm.get("mtime") == meta.get("mtime"):
                unchanged_keys.add(k)
            else:
                modified_keys.add(k)

        # UI 표시에 사용할 FileStatus 업데이트
        for k in unchanged_keys:
            fp = current[k]["path"]
            self.file_infos[fp].status = FileStatus.CACHED
            self.file_infos[fp].chunks = int(cached_files.get(k, {}).get("chunks", 0) or 0)

        need_rebuild_or_delete = bool(deleted_keys or modified_keys)

        # 1) 캐시 로드(필요한 경우)
        loaded_cache = False
        if os.path.exists(cache_dir) and (unchanged_keys or need_rebuild_or_delete):
            loaded_cache = self._load_cache_data(cache_dir, progress_cb)
            if loaded_cache:
                cache_info["vector_id_mode"] = self._vector_id_mode
            if not loaded_cache and unchanged_keys:
                # "추가만" 케이스인데 캐시가 손상되어 로드 불가 -> 전체 재빌드가 안전
                need_rebuild_or_delete = True

        # 2) 수정/삭제 감지 시: 부분 삭제 시도 후 실패 시 전체 재빌드
        if need_rebuild_or_delete:
            affected_keys = set(deleted_keys) | set(modified_keys)

            can_partial_delete = (
                loaded_cache
                and cache_info.get("vector_id_mode") == "doc_id"
                and hasattr(self.vector_store, "delete")
                and self.doc_ids
            )

            if can_partial_delete:
                prefixes = tuple(f"{k}#" for k in affected_keys)
                ids_to_remove = [did for did in self.doc_ids if did.startswith(prefixes)]

                if ids_to_remove and self._delete_from_vector_store(ids_to_remove):
                    # 메모리 리스트에서도 제거
                    keep_mask = [did not in set(ids_to_remove) for did in self.doc_ids]
                    self.documents = [d for d, keep in zip(self.documents, keep_mask) if keep]
                    self.doc_meta = [m for m, keep in zip(self.doc_meta, keep_mask) if keep]
                    self.doc_ids = [did for did in self.doc_ids if did not in set(ids_to_remove)]

                    # 캐시 파일 메타 제거(삭제/수정 대상)
                    for k in affected_keys:
                        cached_files.pop(k, None)

                    # 수정/추가 대상만 재처리해서 재삽입
                    to_process_keys = list(added_keys | modified_keys)
                    to_process_paths = [current[k]["path"] for k in to_process_keys if k in current]

                    if to_process_paths:
                        failed, new_docs, new_files_info, new_texts, new_metas, new_ids = self._extract_and_chunk_docs(
                            folder,
                            to_process_paths,
                            progress_cb,
                            cancel_check,
                            pdf_passwords=pdf_passwords,
                            ocr_engine=ocr_engine,
                        )
                        if cancel_check and cancel_check():
                            return TaskResult(False, "사용자에 의해 취소됨")

                        progress_cb(75, "벡터 인덱스 업데이트...")
                        if not self._update_vector_index(new_docs, new_ids, cancel_check=cancel_check):
                            # 부분 업데이트 실패 시 전체 재빌드로 폴백
                            return self._rebuild_all(
                                folder,
                                list(current.values()),
                                progress_cb,
                                cancel_check,
                                pdf_passwords=pdf_passwords,
                                ocr_engine=ocr_engine,
                            )

                        self.documents.extend(new_texts)
                        self.doc_meta.extend(new_metas)
                        self.doc_ids.extend(new_ids)
                        cached_files.update(new_files_info)

                    cache_info["files"] = cached_files
                    self._build_bm25()
                    progress_cb(90, "캐시 저장...")
                    self._save_cache(cache_dir, cache_info)
                    progress_cb(100, "완료!")

                    failed_items = failed if "failed" in locals() else []
                    return TaskResult(
                        True,
                        f"변경 사항 반영 완료 (삭제 {len(deleted_keys)} / 수정 {len(modified_keys)} / 추가 {len(added_keys)})",
                        {"chunks": len(self.documents), "cached": len(unchanged_keys), "new": len(added_keys) + len(modified_keys)},
                        failed_items,
                    )

            # 부분 삭제 불가/실패: 전체 재빌드
            return self._rebuild_all(
                folder,
                list(current.values()),
                progress_cb,
                cancel_check,
                pdf_passwords=pdf_passwords,
                ocr_engine=ocr_engine,
            )

        # 3) 추가만 처리(안전 증분)
        to_process_keys = list(added_keys)
        to_process_paths = [current[k]["path"] for k in to_process_keys if k in current]

        if not to_process_paths:
            self._build_bm25()
            progress_cb(100, "완료!")
            return TaskResult(
                True,
                f"캐시에서 {len(unchanged_keys)}개 파일 로드",
                {"chunks": len(self.documents), "cached": len(unchanged_keys), "new": 0},
            )

        failed, new_docs, new_files_info, new_texts, new_metas, new_ids = self._extract_and_chunk_docs(
            folder,
            to_process_paths,
            progress_cb,
            cancel_check,
            pdf_passwords=pdf_passwords,
            ocr_engine=ocr_engine,
        )

        if cancel_check and cancel_check():
            return TaskResult(False, "사용자에 의해 취소됨")

        progress_cb(75, "벡터 인덱스 생성/업데이트...")
        if not self._update_vector_index(new_docs, new_ids, cancel_check=cancel_check):
            return TaskResult(False, "인덱스 생성 실패")

        self.documents.extend(new_texts)
        self.doc_meta.extend(new_metas)
        self.doc_ids.extend(new_ids)
        cached_files.update(new_files_info)
        cache_info["files"] = cached_files

        self._build_bm25()
        progress_cb(90, "캐시 저장...")
        self._save_cache(cache_dir, cache_info)
        progress_cb(100, "완료!")

        return TaskResult(
            True,
            f"{len(to_process_paths) - len(failed)}개 처리 완료",
            {"chunks": len(self.documents), "new": len(to_process_paths) - len(failed), "cached": len(unchanged_keys)},
            failed,
        )
    
    def _build_bm25(self):
        if self.documents:
            self.bm25 = BM25Light()
            self.bm25.fit(self.documents)
        else:
            self.bm25 = None
    
    def _load_cache_info(self, cache_dir):
        """캐시 정보 파일 로드"""
        path = os.path.join(cache_dir, "cache_info.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                logger.warning(f"캐시 정보 로드 실패: {path}")
        return {}
    
    def _save_cache(self, cache_dir, cache_info: Dict):
        try:
            os.makedirs(cache_dir, exist_ok=True)
            if not self.vector_store:
                raise RuntimeError("vector_store가 없습니다")

            cache_info = dict(cache_info or {})
            cache_info["schema_version"] = self.CACHE_SCHEMA_VERSION
            cache_info["vector_id_mode"] = self._vector_id_mode
            cache_info["files"] = cache_info.get("files", {}) if isinstance(cache_info.get("files"), dict) else {}

            self.vector_store.save_local(cache_dir)
            with open(os.path.join(cache_dir, "cache_info.json"), "w", encoding="utf-8") as f:
                json.dump(cache_info, f, ensure_ascii=False)
            with open(os.path.join(cache_dir, "docs.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": self.CACHE_SCHEMA_VERSION,
                        "vector_id_mode": self._vector_id_mode,
                        "docs": self.documents,
                        "meta": self.doc_meta,
                        "ids": self.doc_ids,
                    },
                    f,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
    def search(self, query: str, k: int = 3, hybrid: bool = True, op_id: Optional[str] = None) -> TaskResult:
        """하이브리드 검색 수행"""
        if not self.vector_store:
            return TaskResult(False, "문서가 로드되지 않았습니다", op_id=op_id or "", error_code="DOCS_NOT_LOADED")
             
        query = query.strip()
        if len(query) < 2:
            return TaskResult(False, "검색어가 너무 짧습니다 (최소 2자)", op_id=op_id or "", error_code="QUERY_TOO_SHORT")
             
        try:
            k = max(1, min(k, AppConfig.MAX_SEARCH_RESULTS))
            op_id = op_id or new_op_id("SEARCH")
            log = get_op_logger(op_id)
            started = datetime.now()
             
            # 1. 벡터 검색
            vec_results = self.vector_store.similarity_search_with_score(query, k=k*2)
             
            # 2. 결과 정규화 및 결합
            final_results = self._calculate_hybrid_results(query, vec_results, k, hybrid)
            elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
            log.info(f"검색 완료: qlen={len(query)} k={k} hybrid={bool(hybrid)} results={len(final_results)} ({elapsed_ms}ms)")
            with self._diagnostics_lock:
                self.last_op = {
                    "op_id": op_id,
                    "kind": "search",
                    "query_len": len(query),
                    "k": k,
                    "hybrid": bool(hybrid),
                    "results": len(final_results),
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "ts": datetime.now().isoformat(timespec="seconds"),
                }
            return TaskResult(True, "검색 완료", final_results, op_id=op_id)
        except RuntimeError as e:
            get_op_logger(op_id).error(f"FAISS 검색 오류: {e}")
            return TaskResult(
                False,
                "벡터 검색 오류. 문서를 다시 로드해 주세요.",
                op_id=op_id or "",
                error_code="FAISS_SEARCH_FAIL",
                debug=traceback.format_exc(),
            )
        except Exception:
            get_op_logger(op_id).exception("검색 중 오류 발생")
            return TaskResult(
                False,
                "검색 중 내부 오류가 발생했습니다",
                op_id=op_id or "",
                error_code="SEARCH_FAIL",
                debug=traceback.format_exc(),
            )

    def _calculate_hybrid_results(self, query: str, vec_results: List, k: int, hybrid: bool) -> List[Dict]:
        """벡터 및 키워드 검색 결과 결합 및 가중치 적용"""
        combined = {}
        
        # 벡터 결과 정규화
        if vec_results:
            dists = [r[1] for r in vec_results]
            min_d, max_d = min(dists), max(dists)
            rng = max_d - min_d if max_d != min_d else 1.0
            
            for doc, dist in vec_results:
                m = doc.metadata or {}
                doc_id = m.get("id")
                key = doc_id or doc.page_content[:100]
                norm_score = max(0.1, 1 - ((dist - min_d) / (rng + 0.001)))
                combined[key] = {
                    "id": doc_id,
                    "file_key": m.get("file_key"),
                    "chunk_idx": m.get("chunk_idx"),
                    'content': doc.page_content,
                    'source': m.get('source', '?'),
                    'path': m.get('path', ''),
                    'vec_score': norm_score,
                    'bm25_score': 0.0
                }
                
        # BM25 결과 결합
        if hybrid and self.bm25:
            bm_res = self.bm25.search(query, top_k=k*2)
            if bm_res:
                max_bm = max(sc for _, sc in bm_res)
                for idx, sc in bm_res:
                    if 0 <= idx < len(self.documents):
                        doc_id = self.doc_ids[idx] if idx < len(self.doc_ids) else None
                        key = doc_id or self.documents[idx][:100]
                        norm_bm = sc / (max_bm + 0.001)
                        if key in combined:
                            combined[key]['bm25_score'] = norm_bm
                        else:
                            meta = self.doc_meta[idx] if idx < len(self.doc_meta) else {}
                            combined[key] = {
                                "id": doc_id,
                                "file_key": meta.get("file_key"),
                                "chunk_idx": meta.get("chunk_idx"),
                                'content': self.documents[idx],
                                'source': meta.get('source', '?'),
                                'path': meta.get('path', ''),
                                'vec_score': 0.0,
                                'bm25_score': norm_bm
                            }
                            
        # 가중치 적용 및 정렬
        for item in combined.values():
            item['score'] = (AppConfig.VECTOR_WEIGHT * item['vec_score'] + 
                           AppConfig.BM25_WEIGHT * item['bm25_score'])
                           
        return sorted(combined.values(), key=lambda x: x['score'], reverse=True)[:k]
    
    def _identify_files_to_process(self, folder: str, files: List[str], cache_info: Dict) -> Tuple[List[str], List[str]]:
        """(호환용) 추가 파일과 캐시 파일 구분 - v2 스키마 기준."""
        to_process, cached = [], []
        cache_files = (cache_info or {}).get("files") if isinstance(cache_info, dict) else {}
        if not isinstance(cache_files, dict):
            cache_files = {}
        for fp in files:
            key = self._file_key(folder, fp)
            meta = FileUtils.get_metadata(fp)
            cm = cache_files.get(key)
            if meta and cm and cm.get("size") == meta.get("size") and cm.get("mtime") == meta.get("mtime"):
                cached.append(fp)
            else:
                to_process.append(fp)
        return to_process, cached

    def _load_cache_data(self, cache_dir: str, progress_cb):
        """저장된 인덱스와 문서를 캐시에서 로드"""
        if not os.path.exists(os.path.join(cache_dir, "index.faiss")):
            return False
             
        try:
            # allow_dangerous_deserialization 방어: 반드시 cache_root 하위 경로만 로드
            abs_cache_dir = os.path.abspath(cache_dir)
            abs_root = os.path.abspath(self.cache_path)
            if os.path.commonpath([abs_cache_dir, abs_root]) != abs_root:
                logger.warning(f"캐시 경로가 루트 밖입니다. 로드 중단: {abs_cache_dir}")
                return False

            # 프리체크: cache_info.json 스키마가 맞는지 먼저 확인 (docs.json은 매우 클 수 있음)
            cache_info_path = os.path.join(cache_dir, "cache_info.json")
            if not os.path.exists(cache_info_path):
                return False
            try:
                with open(cache_info_path, "r", encoding="utf-8") as f:
                    ci = json.load(f) or {}
                if ci.get("schema_version") != self.CACHE_SCHEMA_VERSION:
                    raise ValueError("캐시 스키마 버전 불일치")
            except Exception:
                logger.warning(f"캐시 프리체크 실패: {cache_dir}")
                return False

            progress_cb(10, "캐시 로드 중...")
            FAISS = _import_attr("langchain_community.vectorstores", "FAISS")
            self.vector_store = FAISS.load_local(
                cache_dir, self.embedding_model, allow_dangerous_deserialization=True
            )
            docs_path = os.path.join(cache_dir, "docs.json")
            if os.path.exists(docs_path):
                with open(docs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("schema_version") != self.CACHE_SCHEMA_VERSION:
                        raise ValueError("캐시 스키마 버전 불일치")
                    self._vector_id_mode = data.get("vector_id_mode", "auto")
                    self.documents = data.get("docs", []) or []
                    self.doc_meta = data.get("meta", []) or []
                    self.doc_ids = data.get("ids", []) or []
                    if len(self.documents) != len(self.doc_meta) or len(self.documents) != len(self.doc_ids):
                        raise ValueError("캐시 문서 데이터 정합성 오류")
            return True
        except Exception:
            logger.exception("캐시 로드 중 오류 발생")
            self.vector_store = None
            self.documents, self.doc_meta, self.doc_ids = [], [], []
            # 손상된 캐시 삭제
            shutil.rmtree(cache_dir, ignore_errors=True)
            logger.info(f"손상된 캐시 삭제됨: {cache_dir}")
            return False

    def _update_vector_index(self, new_docs: List[Any], new_ids: Optional[List[str]] = None, cancel_check=None) -> bool:
        """벡터 인덱스 생성 또는 추가"""
        if not new_docs:
            return self.vector_store is not None
            
        try:
            FAISS = _import_attr("langchain_community.vectorstores", "FAISS")
            if self.vector_store:
                for i in range(0, len(new_docs), AppConfig.BATCH_SIZE):
                    if cancel_check and cancel_check():
                        return False
                    batch_docs = new_docs[i:i + AppConfig.BATCH_SIZE]
                    batch_ids = new_ids[i:i + AppConfig.BATCH_SIZE] if new_ids else None
                    try:
                        if batch_ids is not None:
                            self.vector_store.add_documents(batch_docs, ids=batch_ids)
                        else:
                            self.vector_store.add_documents(batch_docs)
                    except TypeError:
                        # ids 미지원 버전 -> 안정성 위해 모드 다운그레이드
                        self._vector_id_mode = "auto"
                        self.vector_store.add_documents(batch_docs)
            else:
                try:
                    if new_ids is not None:
                        self.vector_store = FAISS.from_documents(new_docs, self.embedding_model, ids=new_ids)
                        self._vector_id_mode = "doc_id"
                    else:
                        self.vector_store = FAISS.from_documents(new_docs, self.embedding_model)
                        self._vector_id_mode = "auto"
                except TypeError:
                    self.vector_store = FAISS.from_documents(new_docs, self.embedding_model)
                    self._vector_id_mode = "auto"
            return True
        except Exception:
            logger.exception("벡터 인덱스 업데이트 실패")
            return False

    def _delete_from_vector_store(self, ids: List[str]) -> bool:
        """가능한 경우 vector_store에서 id 리스트 삭제. 실패하면 False."""
        if not ids or not self.vector_store or not hasattr(self.vector_store, "delete"):
            return False
        try:
            self.vector_store.delete(ids)
            return True
        except TypeError:
            try:
                self.vector_store.delete(ids=ids)
                return True
            except Exception:
                logger.exception("vector_store.delete 실패")
                return False
        except Exception:
            logger.exception("vector_store.delete 실패")
            return False

    def get_file_infos(self): return list(self.file_infos.values())
    def clear_cache(self, reset_memory: bool = True):
        if os.path.exists(self.cache_path):
            shutil.rmtree(self.cache_path, ignore_errors=True)
        if reset_memory:
            self.reset_runtime_state(reset_model=False)
            return TaskResult(True, "디스크+메모리 캐시 삭제 완료")
        return TaskResult(True, "디스크 캐시 삭제 완료")

    def _rebuild_all(
        self,
        folder: str,
        current_items: List[Dict[str, Any]],
        progress_cb,
        cancel_check=None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> TaskResult:
        """수정/삭제가 포함된 경우 안전한 전체 재빌드."""
        cache_dir = self._get_cache_dir(folder)
        shutil.rmtree(cache_dir, ignore_errors=True)

        self.vector_store = None
        self._vector_id_mode = "auto"
        self.documents, self.doc_meta, self.doc_ids = [], [], []

        all_paths = [it["path"] for it in current_items if it.get("path")]
        failed, new_docs, new_files_info, new_texts, new_metas, new_ids = self._extract_and_chunk_docs(
            folder,
            all_paths,
            progress_cb,
            cancel_check,
            pdf_passwords=pdf_passwords,
            ocr_engine=ocr_engine,
        )
        if cancel_check and cancel_check():
            return TaskResult(False, "사용자에 의해 취소됨")

        progress_cb(75, "벡터 인덱스 생성...")
        if not self._update_vector_index(new_docs, new_ids, cancel_check=cancel_check):
            return TaskResult(False, "인덱스 생성 실패")

        self.documents = new_texts
        self.doc_meta = new_metas
        self.doc_ids = new_ids

        cache_info = self._empty_cache_info()
        cache_info["files"] = new_files_info

        self._build_bm25()
        progress_cb(90, "캐시 저장...")
        self._save_cache(cache_dir, cache_info)
        progress_cb(100, "완료!")

        return TaskResult(
            True,
            f"{len(all_paths) - len(failed)}개 처리 완료 (재빌드)",
            {"chunks": len(self.documents), "new": len(all_paths) - len(failed), "cached": 0},
            failed,
        )

    def _extract_and_chunk_docs(
        self,
        folder: str,
        to_process: List[str],
        progress_cb,
        cancel_check=None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> Tuple[List[str], List[Any], Dict[str, Dict[str, Any]], List[str], List[Dict[str, Any]], List[str]]:
        """문서 추출 및 청크 분할"""
        RecursiveCharacterTextSplitter = _import_attr("langchain.text_splitter", "RecursiveCharacterTextSplitter")
        Document = _import_attr("langchain.docstore.document", "Document")

        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""],
            chunk_size=AppConfig.CHUNK_SIZE,
            chunk_overlap=AppConfig.CHUNK_OVERLAP
        )
        failed: List[str] = []
        new_docs: List[Any] = []
        new_cache_files: Dict[str, Dict[str, Any]] = {}
        new_texts: List[str] = []
        new_metas: List[Dict[str, Any]] = []
        new_ids: List[str] = []
        
        for i, fp in enumerate(to_process):
            # 취소 확인
            if cancel_check and cancel_check():
                logger.info("문서 처리 취소됨")
                break
            
            fname = os.path.basename(fp)
            progress_cb(15 + int((i / len(to_process)) * 55), f"처리: {fname}")
            self.file_infos[fp].status = FileStatus.PROCESSING
            try:
                content, error = self.extractor.extract(
                    fp,
                    pdf_password=(pdf_passwords or {}).get(fp),
                    ocr_engine=ocr_engine,
                )
                if error:
                    failed.append(f"{fname} ({error})")
                    self.file_infos[fp].status = FileStatus.FAILED
                    continue
                    
                chunks = splitter.split_text(content.strip())
                if not chunks:
                    failed.append(f"{fname} (빈 내용)")
                    self.file_infos[fp].status = FileStatus.FAILED
                    continue

                file_key = self._file_key(folder, fp)
                chunk_count = 0
                for chunk in chunks:
                    c = chunk.strip()
                    if not c:
                        continue
                    doc_id = f"{file_key}#{chunk_count}"
                    meta = {
                        "id": doc_id,
                        "file_key": file_key,
                        "chunk_idx": chunk_count,
                        "source": fname,
                        "path": fp,
                    }
                    new_docs.append(Document(page_content=c, metadata=meta))
                    new_texts.append(c)
                    new_metas.append(meta)
                    new_ids.append(doc_id)
                    chunk_count += 1
                        
                self.file_infos[fp].status = FileStatus.SUCCESS
                self.file_infos[fp].chunks = chunk_count
                meta = FileUtils.get_metadata(fp)
                if meta:
                    new_cache_files[file_key] = {
                        "size": meta.get("size"),
                        "mtime": meta.get("mtime"),
                        "chunks": chunk_count,
                    }
            except Exception as e:
                logger.exception(f"문서 처리 중 오류: {fp}")
                failed.append(f"{fname} ({e})")
                self.file_infos[fp].status = FileStatus.FAILED
                
        return failed, new_docs, new_cache_files, new_texts, new_metas, new_ids

    def cleanup(self):
        self.reset_runtime_state(reset_model=False)
        gc.collect()
