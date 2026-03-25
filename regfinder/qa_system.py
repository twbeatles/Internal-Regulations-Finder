# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
import tempfile
import threading
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .app_types import (
    AppConfig,
    DiscoveredFile,
    FileInfo,
    FileStatus,
    SearchStats,
    TaskResult,
)
from .bm25 import BM25Index
from .document_extractor import BaseOCREngine, DocumentExtractor, NoOpOCREngine
from .file_utils import FileUtils
from .qa_system_mixins import RegulationQADiagnosticsMixin
from .runtime import (
    _import_attr,
    _import_module,
    get_models_directory,
    get_op_logger,
    logger,
    new_op_id,
    validate_embedding_runtime,
)
from .search_text import (
    matches_path_filter,
    matches_text_filter,
    normalize_path_text,
    normalize_search_text,
    repeated_title_text,
)
from .text_cache import CachedChunk, TextCacheReplacement, TextCacheStore


class RegulationQASystem(RegulationQADiagnosticsMixin):
    CACHE_SCHEMA_VERSION = 3

    def __init__(self):
        self.vector_store = None
        self.embedding_model = None
        self.model_id = None
        self.extractor = DocumentExtractor()
        self.cache_path = os.path.join(tempfile.gettempdir(), "reg_qa_v93")
        self.bm25: BM25Index | None = None
        self.documents: List[str] = []
        self.doc_meta: List[Dict[str, Any]] = []
        self.doc_ids: List[str] = []
        self.doc_index_by_id: Dict[str, int] = {}
        self.doc_search_fields: List[Dict[str, str]] = []
        self.text_cache_revision = 0
        self.current_folder = ""
        self.current_text_cache_path = ""
        self.current_vector_cache_dir = ""
        self._loaded_vector_revision = 0
        self._loaded_vector_context: tuple[str, str] | None = None
        self._vector_id_mode: str = "auto"
        self.file_infos: Dict[str, FileInfo] = {}
        self._lock = threading.Lock()
        self.last_op: Dict[str, Any] = {}
        self._diagnostics_lock = threading.Lock()
        self.last_search_stats = SearchStats()
        self._cache_usage_bytes_snapshot = 0
        self._index_search_mode = ""
        self._memory_warning = False
        self._memory_warning_chunks = 0
        self._vector_ready = False

    def reset_runtime_state(self, reset_model: bool = False):
        self.vector_store = None
        self._vector_id_mode = "auto"
        self.documents.clear()
        self.doc_meta.clear()
        self.doc_ids.clear()
        self.doc_index_by_id.clear()
        self.doc_search_fields.clear()
        self.file_infos.clear()
        self.current_folder = ""
        self.current_text_cache_path = ""
        self.current_vector_cache_dir = ""
        self.text_cache_revision = 0
        self._loaded_vector_revision = 0
        self._loaded_vector_context = None
        self.last_search_stats = SearchStats()
        self._index_search_mode = ""
        self._memory_warning = False
        self._memory_warning_chunks = 0
        self._vector_ready = False
        if self.bm25:
            self.bm25.clear()
        self.bm25 = None
        if reset_model:
            self.embedding_model = None
            self.model_id = None

    def load_model(self, model_name: str, progress_cb=None, op_id: Optional[str] = None) -> TaskResult:
        op_id = op_id or new_op_id("MODEL")
        log = get_op_logger(op_id)
        model_id = AppConfig.AVAILABLE_MODELS.get(model_name, AppConfig.AVAILABLE_MODELS[AppConfig.DEFAULT_MODEL])
        started = datetime.now()
        try:
            if self.embedding_model is not None and self.model_id == model_id:
                elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
                with self._diagnostics_lock:
                    self.last_op = {
                        "op_id": op_id,
                        "kind": "load_model",
                        "model_name": model_name,
                        "device": "cached",
                        "success": True,
                        "elapsed_ms": elapsed_ms,
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                return TaskResult(True, "모델 이미 로드됨", op_id=op_id)

            if progress_cb:
                progress_cb("라이브러리 로드 중...")
            torch = _import_module("torch")
            self._validate_embedding_runtime()
            HuggingFaceEmbeddings = _import_attr("langchain_huggingface", "HuggingFaceEmbeddings")
            if progress_cb:
                progress_cb("모델 로딩 중...")
            cache_dir = get_models_directory()
            os.makedirs(cache_dir, exist_ok=True)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            log.info(f"모델 로드 시작: {model_name} ({device})")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=model_id,
                cache_folder=cache_dir,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )
            self.model_id = model_id
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
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

    def _validate_embedding_runtime(self) -> None:
        validate_embedding_runtime(_import_module)

    def _resolve_search_mode(self, hybrid: bool) -> str:
        vector_ready = bool(self.vector_store)
        bm25_ready = self.bm25 is not None and bool(self.documents)
        if vector_ready and hybrid:
            return "hybrid"
        if vector_ready:
            return "vector_only"
        if bm25_ready:
            return "bm25_only"
        return ""

    def _refresh_runtime_flags(self) -> None:
        self._vector_ready = bool(self.vector_store)
        self._index_search_mode = self._resolve_search_mode(hybrid=True)

    def get_search_mode(self, hybrid: bool = True) -> str:
        return self._resolve_search_mode(hybrid)

    def _update_memory_warning(self) -> None:
        chunk_count = len(self.documents)
        self._memory_warning_chunks = chunk_count
        self._memory_warning = chunk_count > AppConfig.MAX_DOCS_IN_MEMORY

    def _distance_to_score(self, distance: float) -> float:
        return 1.0 / (1.0 + max(float(distance), 0.0))

    def _combine_scores(self, *, vec_score: float, bm25_score: float, search_mode: str) -> float:
        if search_mode == "vector_only":
            return vec_score
        if search_mode == "bm25_only":
            return bm25_score
        return (
            AppConfig.VECTOR_WEIGHT * vec_score
            + AppConfig.BM25_WEIGHT * bm25_score
        )

    def _build_bm25_documents(self) -> List[str]:
        docs: List[str] = []
        for idx, content in enumerate(self.documents):
            meta = self.doc_meta[idx] if idx < len(self.doc_meta) else {}
            source = str(meta.get("source", "") or "")
            docs.append(repeated_title_text(source, content, repeats=2))
        return docs

    def _hash_token(self, value: str) -> str:
        return hashlib.md5(str(value).encode("utf-8")).hexdigest()[:12]

    def _get_folder_token(self, folder: str) -> str:
        return self._hash_token(os.path.normpath(os.path.abspath(folder)))

    def _get_model_token(self) -> str:
        if not self.model_id:
            raise ValueError("모델이 로드되지 않았습니다")
        return self._hash_token(self.model_id)

    def _get_text_cache_path(self, folder: str) -> str:
        folder_token = self._get_folder_token(folder)
        return os.path.join(self.cache_path, "text", folder_token, "text_cache.sqlite")

    def _get_vector_cache_dir(self, folder: str) -> str:
        folder_token = self._get_folder_token(folder)
        model_token = self._get_model_token()
        return os.path.join(self.cache_path, "vector", folder_token, model_token)

    def _get_cache_dir(self, folder: str) -> str:
        return self._get_vector_cache_dir(folder)

    def process_documents(
        self,
        folder: str,
        files: Sequence[str | DiscoveredFile],
        progress_cb,
        cancel_check=None,
        op_id: Optional[str] = None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_options: Optional[Dict[str, Any]] = None,
    ) -> TaskResult:
        if not self.embedding_model:
            return TaskResult(False, "모델이 로드되지 않았습니다", op_id=op_id or "", error_code="MODEL_NOT_LOADED")
        folder = os.path.normpath(os.path.abspath(folder))
        discovered_files = self._coerce_discovered_files(folder, files)
        op_id = op_id or new_op_id("DOCS")
        log = get_op_logger(op_id)
        started = datetime.now()
        log.info(f"문서 처리 시작: folder={folder} files={len(discovered_files)}")
        ocr_engine = self._resolve_ocr_engine(ocr_options)
        with self._lock:
            result = self._process_internal(
                folder,
                discovered_files,
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
                "files": len(discovered_files),
                "success": bool(result.success),
                "elapsed_ms": elapsed_ms,
                "failed_items_count": len(result.failed_items or []),
                "text_cache_revision": self.text_cache_revision,
                "vector_ready": bool((result.data or {}).get("vector_ready", self._vector_ready)),
                "search_mode": str((result.data or {}).get("search_mode", self._index_search_mode)),
                "memory_warning": bool((result.data or {}).get("memory_warning", self._memory_warning)),
                "ts": datetime.now().isoformat(timespec="seconds"),
            }
        log.info(f"문서 처리 완료: success={result.success} elapsed={elapsed_ms}ms failed={len(result.failed_items or [])}")
        return result

    def _coerce_discovered_files(
        self,
        folder: str,
        files: Sequence[str | DiscoveredFile],
    ) -> List[DiscoveredFile]:
        discovered: List[DiscoveredFile] = []
        for item in files:
            if isinstance(item, DiscoveredFile):
                discovered.append(item)
            else:
                discovered.append(FileUtils.build_discovered_file(folder, str(item)))
        discovered.sort(key=lambda item: item.rel_path.lower())
        return discovered

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
        folder: str,
        files: Sequence[DiscoveredFile],
        progress_cb,
        cancel_check=None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> TaskResult:
        self.current_folder = folder
        self.current_text_cache_path = self._get_text_cache_path(folder)
        self.current_vector_cache_dir = self._get_vector_cache_dir(folder)
        self.file_infos.clear()

        current: Dict[str, DiscoveredFile] = {}
        for discovered in files:
            if discovered.file_key in current:
                logger.warning(f"중복 파일 키 감지, 무시됨: {discovered.file_key} ({discovered.path})")
                continue
            current[discovered.file_key] = discovered
            self.file_infos[discovered.path] = FileInfo(
                discovered.path,
                discovered.name,
                discovered.extension,
                discovered.size,
            )

        progress_cb(10, "텍스트 캐시 확인...")
        text_cache = TextCacheStore(self.current_text_cache_path, self.CACHE_SCHEMA_VERSION)
        cached_files = text_cache.get_files()
        cur_keys = set(current.keys())
        cache_keys = set(cached_files.keys())
        deleted_keys = cache_keys - cur_keys
        added_keys = cur_keys - cache_keys
        modified_keys = set()
        unchanged_keys = set()

        for key in (cur_keys & cache_keys):
            discovered = current[key]
            cached = cached_files.get(key) or {}
            same_size = int(cached.get("size", -1)) == discovered.size
            same_mtime = float(cached.get("mtime", -1)) == discovered.mtime
            if same_size and same_mtime:
                cached_fingerprint = str(cached.get("fingerprint", "") or "")
                if cached_fingerprint:
                    try:
                        current_fingerprint = text_cache.compute_file_fingerprint(discovered.path)
                    except OSError:
                        current_fingerprint = ""
                    if current_fingerprint and current_fingerprint == cached_fingerprint:
                        unchanged_keys.add(key)
                        continue
                    modified_keys.add(key)
                    continue
                unchanged_keys.add(key)
            else:
                modified_keys.add(key)

        for key in unchanged_keys:
            discovered = current[key]
            info = self.file_infos.get(discovered.path)
            if info is None:
                continue
            info.status = FileStatus.CACHED
            info.chunks = int((cached_files.get(key) or {}).get("chunks", 0) or 0)

        affected_keys = deleted_keys | modified_keys
        old_chunk_counts = {
            key: int((cached_files.get(key) or {}).get("chunks", 0) or 0)
            for key in affected_keys
        }

        if affected_keys:
            progress_cb(20, "변경 파일 정리 중...")
            text_cache.delete_files(sorted(affected_keys))

        failed: List[str] = []
        replacements: List[TextCacheReplacement] = []
        new_docs: List[Any] = []
        new_ids: List[str] = []
        to_process = [current[key] for key in sorted(added_keys | modified_keys)]
        if to_process:
            failed, replacements, new_docs, _, _, new_ids = self._extract_and_chunk_docs(
                to_process,
                progress_cb,
                cancel_check,
                pdf_passwords=pdf_passwords,
                ocr_engine=ocr_engine,
            )
            if cancel_check and cancel_check():
                return TaskResult(False, "사용자에 의해 취소됨")
            if replacements:
                progress_cb(60, "텍스트 캐시 갱신 중...")
                text_cache.replace_files(replacements)

        text_snapshot = text_cache.snapshot()
        self.text_cache_revision = text_snapshot.revision
        chunks = text_cache.load_chunks()
        self._load_documents_from_chunks(chunks)
        self._build_bm25()
        self._update_memory_warning()

        if cancel_check and cancel_check():
            return TaskResult(False, "사용자에 의해 취소됨")

        removed_doc_ids = self._expand_doc_ids(old_chunk_counts)
        text_changed = bool(deleted_keys or added_keys or modified_keys)
        vector_ready = False
        if self.documents:
            progress_cb(72, "벡터 인덱스 동기화 중...")
            synced = self._sync_vector_index(
                folder,
                text_changed=text_changed,
                removed_doc_ids=removed_doc_ids,
                new_docs=new_docs,
                new_ids=new_ids,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
            )
            vector_ready = bool(synced and self.vector_store)
            if not synced:
                self.vector_store = None
                self._vector_id_mode = "auto"
        else:
            self.vector_store = None
            self._vector_id_mode = "auto"
            self._loaded_vector_revision = self.text_cache_revision
            self._save_vector_meta(self.current_vector_cache_dir, self.text_cache_revision, doc_count=0)
            vector_ready = False

        self._refresh_runtime_flags()
        search_mode = self._resolve_search_mode(hybrid=True)
        summary = {
            "chunks": len(self.documents),
            "cached": len(unchanged_keys),
            "new": len(replacements),
            "text_cache_revision": self.text_cache_revision,
            "vector_ready": bool(vector_ready),
            "search_mode": search_mode,
            "memory_warning": self._memory_warning,
            "memory_warning_chunks": self._memory_warning_chunks,
        }
        progress_cb(100, "완료!")
        if self.documents and not vector_ready and self.bm25 is not None:
            return TaskResult(
                True,
                f"{len(files) - len(failed)}개 처리 완료 (키워드 검색 모드)",
                summary,
                failed,
            )
        return TaskResult(
            True,
            f"{len(files) - len(failed)}개 처리 완료",
            summary,
            failed,
        )

    def _expand_doc_ids(self, chunk_counts: Dict[str, int]) -> List[str]:
        doc_ids: List[str] = []
        for file_key, chunk_count in chunk_counts.items():
            for idx in range(max(0, int(chunk_count))):
                doc_ids.append(f"{file_key}#{idx}")
        return doc_ids

    def _load_documents_from_chunks(self, chunks: Sequence[CachedChunk]) -> None:
        self.documents = []
        self.doc_meta = []
        self.doc_ids = []
        self.doc_index_by_id = {}
        self.doc_search_fields = []
        for idx, chunk in enumerate(chunks):
            meta = {
                "id": chunk.doc_id,
                "file_key": chunk.file_key,
                "chunk_idx": chunk.chunk_idx,
                "source": chunk.source,
                "path": chunk.path,
                "mtime": chunk.mtime,
            }
            self.documents.append(chunk.text)
            self.doc_meta.append(meta)
            self.doc_ids.append(chunk.doc_id)
            self.doc_index_by_id[chunk.doc_id] = idx
            source_lc = normalize_search_text(str(chunk.source or ""))
            path_lc = normalize_path_text(str(chunk.path or ""))
            extension = os.path.splitext(path_lc or source_lc)[1].lower()
            self.doc_search_fields.append(
                {
                    "source": source_lc,
                    "path": path_lc,
                    "extension": extension,
                }
            )
        self._update_memory_warning()

    def _vector_meta_path(self, cache_dir: str) -> str:
        return os.path.join(cache_dir, "vector_meta.json")

    def _load_vector_meta(self, cache_dir: str) -> Dict[str, Any]:
        path = self._vector_meta_path(cache_dir)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.warning(f"벡터 메타 로드 실패: {path}")
            return {}

    def _save_vector_meta(self, cache_dir: str, text_cache_revision: int, *, doc_count: int) -> None:
        os.makedirs(cache_dir, exist_ok=True)
        payload = {
            "schema_version": self.CACHE_SCHEMA_VERSION,
            "model_id": self.model_id,
            "vector_id_mode": self._vector_id_mode,
            "text_cache_revision": int(text_cache_revision),
            "doc_count": int(doc_count),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._vector_meta_path(cache_dir), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _load_vector_cache(self, cache_dir: str, *, expected_revision: Optional[int]) -> bool:
        if not os.path.exists(os.path.join(cache_dir, "index.faiss")):
            return False
        meta = self._load_vector_meta(cache_dir)
        if meta.get("schema_version") != self.CACHE_SCHEMA_VERSION:
            return False
        if meta.get("model_id") != self.model_id:
            return False
        if expected_revision is not None and int(meta.get("text_cache_revision", -1) or -1) != int(expected_revision):
            return False
        try:
            FAISS = _import_attr("langchain_community.vectorstores", "FAISS")
            self.vector_store = FAISS.load_local(
                cache_dir,
                self.embedding_model,
                allow_dangerous_deserialization=True,
            )
            self._vector_id_mode = str(meta.get("vector_id_mode", "doc_id") or "doc_id")
            self.current_vector_cache_dir = cache_dir
            self._loaded_vector_revision = int(meta.get("text_cache_revision", 0) or 0)
            self._loaded_vector_context = (self.current_folder, str(self.model_id or ""))
            self._refresh_runtime_flags()
            return True
        except Exception:
            logger.exception("벡터 캐시 로드 중 오류 발생")
            self.vector_store = None
            self._refresh_runtime_flags()
            return False

    def _save_vector_cache(self, cache_dir: str) -> None:
        if not self.vector_store:
            raise RuntimeError("vector_store가 없습니다")
        os.makedirs(cache_dir, exist_ok=True)
        self.vector_store.save_local(cache_dir)
        self._save_vector_meta(cache_dir, self.text_cache_revision, doc_count=len(self.documents))
        self.current_vector_cache_dir = cache_dir
        self._loaded_vector_revision = self.text_cache_revision
        self._loaded_vector_context = (self.current_folder, str(self.model_id or ""))
        self._refresh_runtime_flags()

    def _sync_vector_index(
        self,
        folder: str,
        *,
        text_changed: bool,
        removed_doc_ids: Sequence[str],
        new_docs: Sequence[Any],
        new_ids: Sequence[str],
        progress_cb,
        cancel_check=None,
    ) -> bool:
        cache_dir = self._get_vector_cache_dir(folder)
        if not text_changed and self._load_vector_cache(cache_dir, expected_revision=self.text_cache_revision):
            return True

        if text_changed and self._try_partial_vector_sync(
            cache_dir,
            removed_doc_ids=removed_doc_ids,
            new_docs=new_docs,
            new_ids=new_ids,
            cancel_check=cancel_check,
        ):
            progress_cb(90, "벡터 캐시 저장 중...")
            self._save_vector_cache(cache_dir)
            return True

        return self._rebuild_vector_index(cache_dir, progress_cb=progress_cb, cancel_check=cancel_check)

    def _try_partial_vector_sync(
        self,
        cache_dir: str,
        *,
        removed_doc_ids: Sequence[str],
        new_docs: Sequence[Any],
        new_ids: Sequence[str],
        cancel_check=None,
    ) -> bool:
        if not self._load_vector_cache(cache_dir, expected_revision=None):
            return False
        if not self.vector_store or self._vector_id_mode != "doc_id" or not hasattr(self.vector_store, "delete"):
            return False
        try:
            if cancel_check and cancel_check():
                return False
            if removed_doc_ids and not self._delete_from_vector_store(list(removed_doc_ids)):
                return False
            if cancel_check and cancel_check():
                return False
            if new_docs and not self._add_documents_to_vector_store(list(new_docs), list(new_ids), cancel_check=cancel_check):
                return False
            return True
        except Exception:
            logger.exception("부분 벡터 인덱스 업데이트 실패")
            return False

    def _rebuild_vector_index(self, cache_dir: str, *, progress_cb, cancel_check=None) -> bool:
        if not self.documents:
            self.vector_store = None
            self._save_vector_meta(cache_dir, self.text_cache_revision, doc_count=0)
            self._refresh_runtime_flags()
            return True
        self.vector_store = None
        self._vector_id_mode = "doc_id"
        progress_cb(82, "벡터 인덱스 재생성 중...")
        if not self._build_vector_store_from_memory(cancel_check=cancel_check):
            return False
        progress_cb(90, "벡터 캐시 저장 중...")
        self._save_vector_cache(cache_dir)
        return True

    def _build_vector_store_from_memory(self, cancel_check=None) -> bool:
        try:
            FAISS = _import_attr("langchain_community.vectorstores", "FAISS")
            Document = self._import_document_class()
            total = len(self.documents)
            first_batch = min(AppConfig.BATCH_SIZE, total)
            batch_docs = [
                Document(page_content=self.documents[idx], metadata=self.doc_meta[idx])
                for idx in range(first_batch)
            ]
            batch_ids = self.doc_ids[:first_batch]
            if not batch_docs:
                self.vector_store = None
                return True
            self.vector_store = FAISS.from_documents(batch_docs, self.embedding_model, ids=batch_ids)
            self._vector_id_mode = "doc_id"
            if first_batch >= total:
                return True
            remaining_docs: List[Any] = []
            remaining_ids: List[str] = []
            for idx in range(first_batch, total):
                if cancel_check and cancel_check():
                    return False
                remaining_docs.append(Document(page_content=self.documents[idx], metadata=self.doc_meta[idx]))
                remaining_ids.append(self.doc_ids[idx])
                if len(remaining_docs) >= AppConfig.BATCH_SIZE:
                    if not self._add_documents_to_vector_store(remaining_docs, remaining_ids, cancel_check=cancel_check):
                        return False
                    remaining_docs = []
                    remaining_ids = []
            if remaining_docs:
                return self._add_documents_to_vector_store(remaining_docs, remaining_ids, cancel_check=cancel_check)
            return True
        except Exception:
            logger.exception("벡터 인덱스 재생성 실패")
            return False

    def _add_documents_to_vector_store(
        self,
        new_docs: List[Any],
        new_ids: Optional[List[str]] = None,
        cancel_check=None,
    ) -> bool:
        if not new_docs:
            return True
        if not self.vector_store:
            return False
        try:
            for offset in range(0, len(new_docs), AppConfig.BATCH_SIZE):
                if cancel_check and cancel_check():
                    return False
                batch_docs = new_docs[offset:offset + AppConfig.BATCH_SIZE]
                batch_ids = new_ids[offset:offset + AppConfig.BATCH_SIZE] if new_ids else None
                if batch_ids is not None:
                    self.vector_store.add_documents(batch_docs, ids=batch_ids)
                else:
                    self.vector_store.add_documents(batch_docs)
            return True
        except TypeError:
            try:
                self._vector_id_mode = "auto"
                self.vector_store.add_documents(new_docs)
                return True
            except Exception:
                logger.exception("벡터 인덱스 추가 실패")
                return False
        except Exception:
            logger.exception("벡터 인덱스 추가 실패")
            return False

    def _delete_from_vector_store(self, ids: List[str]) -> bool:
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

    def _build_bm25(self):
        if self.documents:
            self.bm25 = BM25Index()
            self.bm25.fit(self._build_bm25_documents())
        else:
            self.bm25 = None
        self._refresh_runtime_flags()

    def search(
        self,
        query: str,
        k: int = 3,
        hybrid: bool = True,
        op_id: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        sort_by: str = "score_desc",
        progress_cb: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> TaskResult:
        query = query.strip()
        if len(query) < 2:
            return TaskResult(False, "검색어가 너무 짧습니다 (최소 2자)", op_id=op_id or "", error_code="QUERY_TOO_SHORT")

        search_mode = self._resolve_search_mode(hybrid)
        if not search_mode:
            return TaskResult(False, "문서가 로드되지 않았습니다", op_id=op_id or "", error_code="DOCS_NOT_LOADED")

        op_id = op_id or new_op_id("SEARCH")
        log = get_op_logger(op_id)
        started = datetime.now()
        filters_norm = self._normalize_filters(filters or {})

        def _emit_progress(message: str) -> None:
            if progress_cb is not None:
                progress_cb(str(message))

        def _check_canceled() -> None:
            if cancel_check and cancel_check():
                raise RuntimeError("SEARCH_CANCELED")

        try:
            _emit_progress("검색 조건을 확인하는 중...")
            _check_canceled()
            k = max(1, min(k, AppConfig.MAX_SEARCH_RESULTS))
            vec_results: List[Tuple[Any, float]] = []
            vector_fetch_k = 0
            filtered_out = 0
            if search_mode in {"hybrid", "vector_only"}:
                _emit_progress("벡터 후보를 검색하는 중...")
                _check_canceled()
                vec_results, vector_fetch_k, filtered_out = self._search_vector(query, k, filters_norm)
                _check_canceled()
                _emit_progress("벡터 후보 검색을 마쳤습니다.")
            combined, bm25_candidates = self._calculate_hybrid_results(
                query,
                vec_results,
                max(k * 6, k),
                search_mode,
                filters_norm,
                progress_cb=_emit_progress,
                cancel_check=cancel_check,
            )
            _check_canceled()
            _emit_progress("필터 조건을 적용하는 중...")
            filtered = self._apply_search_filters(combined, filters_norm)
            _check_canceled()
            _emit_progress("최종 결과를 정렬하는 중...")
            final_results = self._sort_results(filtered, sort_by)[:k]
            elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
            self.last_search_stats = SearchStats(
                elapsed_ms=elapsed_ms,
                vector_fetch_k=vector_fetch_k,
                bm25_candidates=bm25_candidates,
                filtered_out=filtered_out,
                result_count=len(final_results),
                query_len=len(query),
                search_mode=search_mode,
                vector_ready=bool(self.vector_store),
                filters=dict(filters_norm),
            )
            log.info(
                "검색 완료: qlen=%s k=%s mode=%s results=%s fetch_k=%s bm25_candidates=%s (%sms)",
                len(query),
                k,
                search_mode,
                len(final_results),
                vector_fetch_k,
                bm25_candidates,
                elapsed_ms,
            )
            with self._diagnostics_lock:
                self.last_op = {
                    "op_id": op_id,
                    "kind": "search",
                    "query_len": len(query),
                    "k": k,
                    "hybrid": bool(hybrid),
                    "results": len(final_results),
                    "sort_by": sort_by,
                    "filters": dict(filters_norm),
                    "search_mode": search_mode,
                    "vector_ready": bool(self.vector_store),
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "vector_fetch_k": vector_fetch_k,
                    "bm25_candidates": bm25_candidates,
                    "filtered_out": filtered_out,
                    "ts": datetime.now().isoformat(timespec="seconds"),
                }
            return TaskResult(True, "검색 완료", final_results, op_id=op_id)
        except RuntimeError as e:
            if str(e) == "SEARCH_CANCELED":
                elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
                self.last_search_stats = SearchStats(
                    elapsed_ms=elapsed_ms,
                    vector_fetch_k=0,
                    bm25_candidates=0,
                    filtered_out=0,
                    result_count=0,
                    query_len=len(query),
                    search_mode=search_mode,
                    vector_ready=bool(self.vector_store),
                    filters=dict(filters_norm),
                )
                with self._diagnostics_lock:
                    self.last_op = {
                        "op_id": op_id,
                        "kind": "search",
                        "query_len": len(query),
                        "k": k,
                        "hybrid": bool(hybrid),
                        "results": 0,
                        "sort_by": sort_by,
                        "filters": dict(filters_norm),
                        "search_mode": search_mode,
                        "vector_ready": bool(self.vector_store),
                        "success": False,
                        "status": "canceled",
                        "elapsed_ms": elapsed_ms,
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                return TaskResult(False, "검색이 취소되었습니다", op_id=op_id, error_code="SEARCH_CANCELED")
            log.error(f"FAISS 검색 오류: {e}")
            return TaskResult(
                False,
                "벡터 검색 오류. 문서를 다시 로드해 주세요.",
                op_id=op_id,
                error_code="FAISS_SEARCH_FAIL",
                debug=traceback.format_exc(),
            )
        except Exception:
            log.exception("검색 중 오류 발생")
            return TaskResult(
                False,
                "검색 중 내부 오류가 발생했습니다",
                op_id=op_id,
                error_code="SEARCH_FAIL",
                debug=traceback.format_exc(),
            )

    def _normalize_filters(self, filters: Dict[str, str]) -> Dict[str, str]:
        return {
            "extension": str(filters.get("extension", "") or "").strip().lower(),
            "filename": normalize_search_text(str(filters.get("filename", "") or "")),
            "path": normalize_path_text(str(filters.get("path", "") or "")),
        }

    def _has_filters(self, filters: Dict[str, str]) -> bool:
        return bool(filters.get("extension") or filters.get("filename") or filters.get("path"))

    def _matches_doc_filters(self, doc_idx: int, filters: Dict[str, str]) -> bool:
        if not self._has_filters(filters):
            return True
        if not (0 <= doc_idx < len(self.doc_search_fields)):
            return False
        fields = self.doc_search_fields[doc_idx]
        if filters["extension"] and fields["extension"] != filters["extension"]:
            return False
        if filters["filename"] and not matches_text_filter(fields["source"], filters["filename"]):
            return False
        if filters["path"] and not matches_path_filter(fields["path"], filters["path"]):
            return False
        return True

    def _search_vector(
        self,
        query: str,
        k: int,
        filters: Dict[str, str],
    ) -> Tuple[List[Tuple[Any, float]], int, int]:
        vector_store = self.vector_store
        if vector_store is None:
            return [], 0, 0
        total_docs = len(self.documents)
        if total_docs <= 0:
            return [], 0, 0
        fetch_k = min(total_docs, max(k * 2, 1))
        has_filters = self._has_filters(filters)
        if has_filters:
            fetch_k = min(total_docs, max(k * 4, 20))
        max_fetch = total_docs if has_filters else min(total_docs, max(fetch_k, AppConfig.MAX_VECTOR_FETCH))
        while True:
            raw_results = vector_store.similarity_search_with_score(query, k=fetch_k)
            filtered_results: List[Tuple[Any, float]] = []
            filtered_out = 0
            distinct_files: set[str] = set()
            for doc, dist in raw_results:
                metadata = doc.metadata or {}
                doc_id = str(metadata.get("id", "") or "")
                doc_idx = self.doc_index_by_id.get(doc_id, -1)
                if has_filters and (doc_idx < 0 or not self._matches_doc_filters(doc_idx, filters)):
                    filtered_out += 1
                    continue
                filtered_results.append((doc, dist))
                file_key = str(metadata.get("file_key", "") or doc_id or metadata.get("path", "") or metadata.get("source", ""))
                if file_key:
                    distinct_files.add(file_key)
            if len(distinct_files) >= k or fetch_k >= max_fetch or len(raw_results) < fetch_k:
                return filtered_results, fetch_k, filtered_out
            fetch_k = min(max_fetch, fetch_k * 2)

    def _default_rank_key(self, item: Dict[str, Any]) -> tuple[float, int, float]:
        return (
            float(item.get("score", 0.0) or 0.0),
            int(item.get("match_count", 0) or 0),
            float(item.get("mtime", 0) or 0.0),
        )

    def _aggregate_file_results(
        self,
        chunk_results: Sequence[Dict[str, Any]],
        *,
        search_mode: str,
        progress_cb: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        total = len(chunk_results)
        for idx, item in enumerate(chunk_results):
            if cancel_check and cancel_check():
                raise RuntimeError("SEARCH_CANCELED")
            if progress_cb and total > 0 and idx % 25 == 0:
                progress_cb(f"파일 결과 집계 중... {min(idx + 1, total)}/{total}")
            file_key = str(item.get("file_key", "") or item.get("id", "") or item.get("path", "") or item.get("source", "?"))
            chunk_id = str(item.get("id", "") or f"{file_key}#{item.get('chunk_idx', 0)}")
            chunk_idx = int(item.get("chunk_idx", 0) or 0)
            chunk_score = self._combine_scores(
                vec_score=float(item.get("vec_score", 0.0) or 0.0),
                bm25_score=float(item.get("bm25_score", 0.0) or 0.0),
                search_mode=search_mode,
            )
            existing = grouped.get(file_key)
            if existing is None:
                grouped[file_key] = {
                    "id": chunk_id,
                    "file_key": file_key,
                    "chunk_idx": item.get("chunk_idx"),
                    "snippet_chunk_idx": int(item.get("chunk_idx", 0) or 0),
                    "content": item.get("content", ""),
                    "source": item.get("source", "?"),
                    "path": item.get("path", ""),
                    "mtime": item.get("mtime"),
                    "vec_score": float(item.get("vec_score", 0.0) or 0.0),
                    "bm25_score": float(item.get("bm25_score", 0.0) or 0.0),
                    "score": chunk_score,
                    "match_count": 1,
                    "_best_chunk_score": chunk_score,
                    "_chunk_ids": {chunk_id},
                    "_matched_chunk_indices": {chunk_idx},
                    "_matched_doc_ids": {chunk_id},
                }
                continue

            existing["vec_score"] = max(float(existing.get("vec_score", 0.0) or 0.0), float(item.get("vec_score", 0.0) or 0.0))
            existing["bm25_score"] = max(float(existing.get("bm25_score", 0.0) or 0.0), float(item.get("bm25_score", 0.0) or 0.0))
            existing["score"] = self._combine_scores(
                vec_score=float(existing.get("vec_score", 0.0) or 0.0),
                bm25_score=float(existing.get("bm25_score", 0.0) or 0.0),
                search_mode=search_mode,
            )
            chunk_ids = existing["_chunk_ids"]
            if chunk_id not in chunk_ids:
                chunk_ids.add(chunk_id)
                existing["match_count"] = int(existing.get("match_count", 0) or 0) + 1
                existing["_matched_chunk_indices"].add(chunk_idx)
                existing["_matched_doc_ids"].add(chunk_id)
            best_chunk_score = float(existing.get("_best_chunk_score", 0.0) or 0.0)
            if chunk_score > best_chunk_score or (
                chunk_score == best_chunk_score
                and chunk_idx < int(existing.get("snippet_chunk_idx", 0) or 0)
            ):
                existing["id"] = chunk_id
                existing["chunk_idx"] = item.get("chunk_idx")
                existing["snippet_chunk_idx"] = chunk_idx
                existing["content"] = item.get("content", "")
                existing["_best_chunk_score"] = chunk_score

        aggregated: List[Dict[str, Any]] = []
        for item in grouped.values():
            item["matched_chunk_indices"] = sorted(int(value) for value in item.pop("_matched_chunk_indices", set()))
            item["matched_doc_ids"] = sorted(str(value) for value in item.pop("_matched_doc_ids", set()))
            item.pop("_best_chunk_score", None)
            item.pop("_chunk_ids", None)
            aggregated.append(item)
        return sorted(aggregated, key=self._default_rank_key, reverse=True)

    def _calculate_hybrid_results(
        self,
        query: str,
        vec_results: List[Tuple[Any, float]],
        k: int,
        search_mode: str,
        filters: Dict[str, str],
        progress_cb: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        combined: Dict[str, Dict[str, Any]] = {}

        if search_mode in {"hybrid", "vector_only"} and vec_results:
            if progress_cb:
                progress_cb("벡터 후보를 파일 단위로 정리하는 중...")
            for doc, dist in vec_results:
                if cancel_check and cancel_check():
                    raise RuntimeError("SEARCH_CANCELED")
                metadata = doc.metadata or {}
                doc_id = str(metadata.get("id", "") or "")
                key = doc_id or doc.page_content[:100]
                norm_score = self._distance_to_score(float(dist))
                combined[key] = {
                    "id": doc_id,
                    "file_key": metadata.get("file_key"),
                    "chunk_idx": metadata.get("chunk_idx"),
                    "content": doc.page_content,
                    "source": metadata.get("source", "?"),
                    "path": metadata.get("path", ""),
                    "mtime": metadata.get("mtime"),
                    "vec_score": norm_score,
                    "bm25_score": 0.0,
                }

        bm25_candidates = 0
        if search_mode in {"hybrid", "bm25_only"} and self.bm25:
            if cancel_check and cancel_check():
                raise RuntimeError("SEARCH_CANCELED")
            allow_doc = None
            if self._has_filters(filters):
                allow_doc = lambda idx: self._matches_doc_filters(idx, filters)
            if progress_cb:
                progress_cb("키워드 후보 수를 계산하는 중...")
            bm25_candidates = self.bm25.candidate_count(query, allow_doc=allow_doc)
            if cancel_check and cancel_check():
                raise RuntimeError("SEARCH_CANCELED")
            if progress_cb:
                progress_cb("키워드 후보를 정렬하는 중...")
            bm_res = self.bm25.search(query, top_k=min(len(self.documents), max(k * 8, 50)), allow_doc=allow_doc)
            if bm_res:
                max_bm = max(score for _, score in bm_res)
                for idx, score in bm_res:
                    if cancel_check and cancel_check():
                        raise RuntimeError("SEARCH_CANCELED")
                    if not (0 <= idx < len(self.documents)):
                        continue
                    doc_id = self.doc_ids[idx]
                    key = doc_id or self.documents[idx][:100]
                    norm_bm = score / (max_bm + 0.001)
                    if key in combined:
                        combined[key]["bm25_score"] = norm_bm
                    else:
                        meta = self.doc_meta[idx]
                        combined[key] = {
                            "id": doc_id,
                            "file_key": meta.get("file_key"),
                            "chunk_idx": meta.get("chunk_idx"),
                            "content": self.documents[idx],
                            "source": meta.get("source", "?"),
                            "path": meta.get("path", ""),
                            "mtime": meta.get("mtime"),
                            "vec_score": 0.0,
                            "bm25_score": norm_bm,
                        }

        for item in combined.values():
            item["score"] = self._combine_scores(
                vec_score=float(item.get("vec_score", 0.0) or 0.0),
                bm25_score=float(item.get("bm25_score", 0.0) or 0.0),
                search_mode=search_mode,
            )

        return self._aggregate_file_results(
            list(combined.values()),
            search_mode=search_mode,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        ), bm25_candidates

    def _apply_search_filters(self, results: List[Dict[str, Any]], filters: Dict[str, str]) -> List[Dict[str, Any]]:
        filters_norm = self._normalize_filters(filters)
        if not self._has_filters(filters_norm):
            return results

        filtered: List[Dict[str, Any]] = []
        for item in results:
            source = normalize_search_text(str(item.get("source", "") or ""))
            path = normalize_path_text(str(item.get("path", "") or ""))
            ext = os.path.splitext(path or source)[1].lower()

            if filters_norm["extension"] and ext != filters_norm["extension"]:
                continue
            if filters_norm["filename"] and not matches_text_filter(source, filters_norm["filename"]):
                continue
            if filters_norm["path"] and not matches_path_filter(path, filters_norm["path"]):
                continue
            filtered.append(item)
        return filtered

    def _sort_results(self, results: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        if sort_by == "filename_asc":
            return sorted(results, key=lambda item: str(item.get("source", "") or "").lower())
        if sort_by == "mtime_desc":
            return sorted(results, key=lambda item: float(item.get("mtime", 0) or 0), reverse=True)
        return sorted(results, key=self._default_rank_key, reverse=True)

    def get_file_infos(self):
        return list(self.file_infos.values())

    def get_chunks_for_file_key(self, file_key: str) -> List[Dict[str, Any]]:
        target = str(file_key or "")
        if not target:
            return []
        chunks: List[Dict[str, Any]] = []
        for idx, meta in enumerate(self.doc_meta):
            if str(meta.get("file_key", "") or "") != target:
                continue
            chunks.append(
                {
                    "id": str(meta.get("id", "") or ""),
                    "file_key": target,
                    "chunk_idx": int(meta.get("chunk_idx", 0) or 0),
                    "content": self.documents[idx] if 0 <= idx < len(self.documents) else "",
                    "source": str(meta.get("source", "") or ""),
                    "path": str(meta.get("path", "") or ""),
                    "mtime": meta.get("mtime"),
                }
            )
        return sorted(chunks, key=lambda item: int(item.get("chunk_idx", 0) or 0))

    def clear_cache(self, reset_memory: bool = True):
        if os.path.exists(self.cache_path):
            shutil.rmtree(self.cache_path, ignore_errors=True)
        self._cache_usage_bytes_snapshot = 0
        if reset_memory:
            self.reset_runtime_state(reset_model=False)
            return TaskResult(True, "디스크+메모리 캐시 삭제 완료")
        return TaskResult(True, "디스크 캐시 삭제 완료")

    def clear_folder_cache(self, folder: str) -> None:
        folder = os.path.normpath(os.path.abspath(folder))
        text_dir = os.path.dirname(self._get_text_cache_path(folder))
        vector_root = os.path.join(self.cache_path, "vector", self._get_folder_token(folder))
        shutil.rmtree(text_dir, ignore_errors=True)
        shutil.rmtree(vector_root, ignore_errors=True)

    def _extract_and_chunk_docs(
        self,
        to_process: Sequence[DiscoveredFile],
        progress_cb,
        cancel_check=None,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> Tuple[
        List[str],
        List[TextCacheReplacement],
        List[Any],
        List[str],
        List[Dict[str, Any]],
        List[str],
    ]:
        RecursiveCharacterTextSplitter = self._import_text_splitter()
        Document = self._import_document_class()
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""],
            chunk_size=AppConfig.CHUNK_SIZE,
            chunk_overlap=AppConfig.CHUNK_OVERLAP,
        )
        failed: List[str] = []
        replacements: List[TextCacheReplacement] = []
        new_docs: List[Any] = []
        new_texts: List[str] = []
        new_metas: List[Dict[str, Any]] = []
        new_ids: List[str] = []

        total = max(1, len(to_process))
        for idx, discovered in enumerate(to_process):
            if cancel_check and cancel_check():
                logger.info("문서 처리 취소됨")
                break

            progress_cb(15 + int((idx / total) * 40), f"처리: {discovered.name}")
            info = self.file_infos.get(discovered.path)
            if info is not None:
                info.status = FileStatus.PROCESSING

            try:
                content, error = self.extractor.extract(
                    discovered.path,
                    pdf_password=(pdf_passwords or {}).get(discovered.path),
                    ocr_engine=ocr_engine,
                )
                if error:
                    failed.append(f"{discovered.name} ({error})")
                    if info is not None:
                        info.status = FileStatus.FAILED
                        info.error = error
                    continue

                chunks = splitter.split_text(content.strip())
                if not chunks:
                    failed.append(f"{discovered.name} (빈 내용)")
                    if info is not None:
                        info.status = FileStatus.FAILED
                        info.error = "빈 내용"
                    continue

                cached_chunks: List[CachedChunk] = []
                chunk_count = 0
                for raw_chunk in chunks:
                    chunk = raw_chunk.strip()
                    if not chunk:
                        continue
                    doc_id = f"{discovered.file_key}#{chunk_count}"
                    meta = {
                        "id": doc_id,
                        "file_key": discovered.file_key,
                        "chunk_idx": chunk_count,
                        "source": discovered.name,
                        "path": discovered.path,
                        "mtime": discovered.mtime,
                    }
                    cached_chunks.append(
                        CachedChunk(
                            doc_id=doc_id,
                            file_key=discovered.file_key,
                            chunk_idx=chunk_count,
                            text=chunk,
                            source=discovered.name,
                            path=discovered.path,
                            mtime=discovered.mtime,
                        )
                    )
                    new_docs.append(Document(page_content=chunk, metadata=meta))
                    new_texts.append(chunk)
                    new_metas.append(meta)
                    new_ids.append(doc_id)
                    chunk_count += 1

                replacements.append(
                    TextCacheReplacement(
                        file=discovered,
                        status="ready",
                        chunks=cached_chunks,
                    )
                )
                if info is not None:
                    info.status = FileStatus.SUCCESS
                    info.chunks = chunk_count
                    info.error = ""
            except Exception as e:
                logger.exception(f"문서 처리 중 오류: {discovered.path}")
                failed.append(f"{discovered.name} ({e})")
                if info is not None:
                    info.status = FileStatus.FAILED
                    info.error = str(e)

        return failed, replacements, new_docs, new_texts, new_metas, new_ids

    def _import_text_splitter(self):
        try:
            return _import_attr("langchain_text_splitters", "RecursiveCharacterTextSplitter")
        except ImportError:
            return _import_attr("langchain.text_splitter", "RecursiveCharacterTextSplitter")

    def _import_document_class(self):
        try:
            return _import_attr("langchain_core.documents", "Document")
        except ImportError:
            return _import_attr("langchain.docstore.document", "Document")

    def cleanup(self):
        self.reset_runtime_state(reset_model=False)
        gc.collect()
