# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from regfinder.app_types import AppConfig
from regfinder.bm25 import BM25Index
from regfinder.file_utils import FileUtils
from regfinder.qa_system import RegulationQASystem
from regfinder.text_cache import CachedChunk, TextCacheReplacement, TextCacheStore


class _FakeSplitter:
    def __init__(self, **_: object) -> None:
        pass

    def split_text(self, text: str):
        return [text]


class _FakeDocument:
    def __init__(self, page_content: str, metadata: dict[str, object]):
        self.page_content = page_content
        self.metadata = metadata


class _FakeVectorStore:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.deleted: list[str] = []
        self.added: list[str] = []

    def similarity_search_with_score(self, query: str, k: int) -> list[tuple[object, float]]:
        self.calls.append(k)
        return []

    def save_local(self, path: str) -> None:
        cache_dir = Path(path)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "index.faiss").write_bytes(b"faiss")
        (cache_dir / "index.pkl").write_bytes(b"meta")

    def delete(self, ids):
        self.deleted.extend(list(ids))

    def add_documents(self, docs, ids=None):
        self.added.extend(list(ids or []))


def test_text_cache_snapshot_uses_schema_v3(tmp_path):
    sqlite_path = tmp_path / "text_cache.sqlite"
    store = TextCacheStore(str(sqlite_path), schema_version=3)
    sample = tmp_path / "sample.txt"
    sample.write_text("sample text", encoding="utf-8")
    file = FileUtils.build_discovered_file(str(tmp_path), str(sample))

    replacement = TextCacheReplacement(
        file=file,
        status="ready",
        chunks=[
            CachedChunk(
                doc_id=f"{file.file_key}#0",
                file_key=file.file_key,
                chunk_idx=0,
                text="sample text",
                source=file.name,
                path=file.path,
                mtime=file.mtime,
            )
        ],
    )
    store.replace_files([replacement])

    snapshot = store.snapshot()

    assert snapshot.schema_version == 3
    assert snapshot.revision == 1
    assert snapshot.cached_files == 1
    assert snapshot.cached_chunks == 1


def test_process_documents_reuses_text_cache_when_model_changes(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.txt"
    fp.write_text("사내 규정 본문", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.embedding_model = object()
    qa.model_id = "demo/model-a"
    extractor_calls: list[str] = []

    class _FakeExtractor:
        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            extractor_calls.append(path)
            return "사내 규정 본문", None

    def fake_build_vector(self, cancel_check=None):
        self.vector_store = _FakeVectorStore()
        return True

    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", fake_build_vector)
    qa.extractor = cast(Any, _FakeExtractor())

    discovered_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    result1 = qa.process_documents(str(folder), discovered_files, lambda *_: None)

    assert result1.success is True
    assert extractor_calls == [str(fp)]
    first_revision = qa.text_cache_revision

    qa.model_id = "demo/model-b"
    qa.vector_store = None
    result2 = qa.process_documents(str(folder), discovered_files, lambda *_: None)

    assert result2.success is True
    assert extractor_calls == [str(fp)]
    assert qa.text_cache_revision == first_revision
    assert (Path(qa.cache_path) / "text").exists()
    assert (Path(qa.cache_path) / "vector").exists()


def test_load_model_skips_same_model_reload(monkeypatch, tmp_path):
    calls: list[str] = []

    class _FakeTorch:
        class cuda:
            @staticmethod
            def is_available() -> bool:
                return False

    class _FakeEmbeddings:
        def __init__(self, model_name: str, **_: object):
            calls.append(model_name)

    def fake_import_module(name: str):
        if name == "torch":
            return _FakeTorch
        return object()

    monkeypatch.setattr("regfinder.qa_system._import_module", fake_import_module)
    monkeypatch.setattr(
        "regfinder.qa_system._import_attr",
        lambda module, attr: _FakeEmbeddings if module == "langchain_huggingface" and attr == "HuggingFaceEmbeddings" else None,
    )
    monkeypatch.setattr("regfinder.qa_system.get_models_directory", lambda: str(tmp_path / "models"))

    qa = RegulationQASystem()
    result1 = qa.load_model(AppConfig.DEFAULT_MODEL)
    result2 = qa.load_model(AppConfig.DEFAULT_MODEL)

    assert result1.success is True
    assert result2.success is True
    assert "이미 로드" in result2.message
    assert len(calls) == 1


def test_search_vector_expands_fetch_when_filters_remove_top_results():
    qa = RegulationQASystem()
    docs = []
    qa.documents = []
    qa.doc_meta = []
    qa.doc_ids = []
    qa.doc_index_by_id = {}
    qa.doc_search_fields = []
    for idx in range(30):
        ext = ".pdf" if idx < 25 else ".txt"
        source = f"file{idx}{ext}"
        path = f"C:/docs/{source}"
        doc_id = f"doc#{idx}"
        meta = {"id": doc_id, "source": source, "path": path, "mtime": float(idx)}
        docs.append(SimpleNamespace(page_content=f"content {idx}", metadata=meta))
        qa.documents.append(f"content {idx}")
        qa.doc_meta.append(meta)
        qa.doc_ids.append(doc_id)
        qa.doc_index_by_id[doc_id] = idx
        qa.doc_search_fields.append({"source": source.lower(), "path": path.lower(), "extension": ext})

    class _SearchVectorStore(_FakeVectorStore):
        def similarity_search_with_score(self, query: str, k: int):
            self.calls.append(k)
            return [(docs[idx], float(idx)) for idx in range(min(k, len(docs)))]

    qa.vector_store = _SearchVectorStore()

    results, fetch_k, filtered_out = qa._search_vector("규정", 1, {"extension": ".txt", "filename": "", "path": ""})

    assert qa.vector_store.calls == [20, 30]
    assert fetch_k == 30
    assert len(results) >= 1
    assert filtered_out > 0
    assert results[0][0].metadata["source"].endswith(".txt")


def test_bm25_index_respects_filtered_candidates():
    bm25 = BM25Index()
    bm25.fit(["복리 규정 안내", "휴가 규정 안내", "인사 규정 안내"])

    allow_doc = lambda idx: idx == 1
    results = bm25.search("휴가 규정", top_k=5, allow_doc=allow_doc)

    assert bm25.candidate_count("휴가 규정", allow_doc=allow_doc) == 1
    assert len(results) == 1
    assert results[0][0] == 1
