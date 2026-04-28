# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import zipfile

from regfinder.app_types import AppConfig
from regfinder.bm25 import BM25Index
from regfinder.document_extractor import DocumentExtractor
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


def test_diagnostics_zip_excludes_text_cache_by_default_and_includes_on_request(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.txt"
    fp.write_text("sample text", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.current_folder = str(folder)
    qa.current_text_cache_path = qa._get_text_cache_path(str(folder))
    store = TextCacheStore(qa.current_text_cache_path, schema_version=qa.CACHE_SCHEMA_VERSION)
    file = FileUtils.build_discovered_file(str(folder), str(fp))
    store.replace_files(
        [
            TextCacheReplacement(
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
        ]
    )
    monkeypatch.setattr("regfinder.qa_system_mixins.get_config_path", lambda: str(tmp_path / "config.json"))
    monkeypatch.setattr("regfinder.qa_system_mixins.get_history_path", lambda: str(tmp_path / "search_history.json"))
    monkeypatch.setattr("regfinder.qa_system_mixins.get_logs_directory", lambda: str(tmp_path / "logs"))

    default_zip = tmp_path / "diag-default.zip"
    include_zip = tmp_path / "diag-include.zip"

    assert qa.export_diagnostics_zip(str(default_zip)).success is True
    assert qa.export_diagnostics_zip(str(include_zip), include_text_cache=True).success is True

    with zipfile.ZipFile(default_zip) as zf:
        assert "cache/text_cache.sqlite" not in zf.namelist()
    with zipfile.ZipFile(include_zip) as zf:
        assert "cache/text_cache.sqlite" in zf.namelist()


def test_model_less_diagnostics_include_text_cache(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.txt"
    fp.write_text("sample text", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.current_folder = str(folder)
    store = TextCacheStore(qa._get_text_cache_path(str(folder)), schema_version=qa.CACHE_SCHEMA_VERSION)
    file = FileUtils.build_discovered_file(str(folder), str(fp))
    store.replace_files(
        [
            TextCacheReplacement(
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
        ]
    )
    monkeypatch.setattr("regfinder.qa_system_mixins.ModelInventory.snapshot", lambda self: {})

    status = qa.get_index_status(str(folder))
    diag = qa.collect_diagnostics()

    assert status["cached_files"] == 1
    assert status["cached_chunks"] == 1
    assert diag["cache_summary"]["available"] is True
    assert diag["cache_summary"]["files"] == 1


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


def test_process_documents_builds_bm25_index_without_loaded_model(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.txt"
    fp.write_text("휴가 규정 본문", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")

    class _FakeExtractor:
        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            return Path(path).read_text(encoding="utf-8"), None

    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    qa.extractor = cast(Any, _FakeExtractor())

    discovered_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    result = qa.process_documents(str(folder), discovered_files, lambda *_: None)

    assert result.success is True
    assert result.data["vector_ready"] is False
    assert result.data["search_mode"] == "bm25_only"
    assert qa.current_vector_cache_dir == ""

    search_result = qa.search("휴가규정", k=3, hybrid=True)

    assert search_result.success is True
    assert qa.last_search_stats.search_mode == "bm25_only"


def test_process_documents_preserves_pdf_page_metadata(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.pdf"
    fp.write_bytes(b"%PDF-1.4")

    class _FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        is_encrypted = False
        pages = [_FakePage("첫 페이지 휴가"), _FakePage("둘째 페이지 규정")]

        def __init__(self, path: str):
            pass

        def decrypt(self, password: str):
            return True

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.extractor = cast(Any, DocumentExtractor(pdf_reader_factory=_FakeReader))
    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)

    files = FileUtils.discover_files(str(folder), recursive=False, supported_extensions=AppConfig.SUPPORTED_EXTENSIONS)
    result = qa.process_documents(str(folder), files, lambda *_: None)
    search = qa.search("휴가", k=3, hybrid=True)

    assert result.success is True
    assert qa.doc_meta[0]["page_start"] == 1
    assert qa.get_chunks_for_file_key("sample.pdf")[0]["page_start"] == 1
    assert search.success is True
    assert search.data[0]["page_start"] == 1


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


def test_load_model_syncs_existing_bm25_index_to_vector(monkeypatch, tmp_path):
    class _FakeTorch:
        class cuda:
            @staticmethod
            def is_available() -> bool:
                return False

    class _FakeEmbeddings:
        def __init__(self, **_: object):
            pass

    sync_calls = []

    def fake_import_module(name: str):
        if name == "torch":
            return _FakeTorch
        return object()

    def fake_import_attr(module: str, attr: str):
        if module == "langchain_huggingface" and attr == "HuggingFaceEmbeddings":
            return _FakeEmbeddings
        return object()

    def fake_sync(self, folder, **kwargs):
        sync_calls.append((folder, kwargs["text_changed"]))
        self.vector_store = _FakeVectorStore()
        return True

    monkeypatch.setattr("regfinder.qa_system._import_module", fake_import_module)
    monkeypatch.setattr("regfinder.qa_system._import_attr", fake_import_attr)
    monkeypatch.setattr("regfinder.qa_system.get_models_directory", lambda: str(tmp_path / "models"))
    monkeypatch.setattr(RegulationQASystem, "_sync_vector_index", fake_sync)

    qa = RegulationQASystem()
    qa.current_folder = str(tmp_path)
    qa.documents = ["휴가 규정"]
    qa.doc_meta = [{"id": "doc#0", "file_key": "doc", "chunk_idx": 0, "source": "doc.txt", "path": "doc.txt"}]
    qa.doc_ids = ["doc#0"]
    qa._build_bm25()

    result = qa.load_model(AppConfig.DEFAULT_MODEL)

    assert result.success is True
    assert sync_calls == [(str(tmp_path), False)]
    assert qa.vector_store is not None


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

    results, fetch_k, filtered_out, limit_reached = qa._search_vector("규정", 1, {"extension": ".txt", "filename": "", "path": ""})

    assert qa.vector_store.calls == [20, 30]
    assert fetch_k == 30
    assert len(results) >= 1
    assert filtered_out > 0
    assert limit_reached is False
    assert results[0][0].metadata["source"].endswith(".txt")


def test_bm25_index_respects_filtered_candidates():
    bm25 = BM25Index()
    bm25.fit(["복리 규정 안내", "휴가 규정 안내", "인사 규정 안내"])

    allow_doc = lambda idx: idx == 1
    results = bm25.search("휴가 규정", top_k=5, allow_doc=allow_doc)

    assert bm25.candidate_count("휴가 규정", allow_doc=allow_doc) == 1
    assert len(results) == 1
    assert results[0][0] == 1


def test_bm25_index_supports_compound_and_particle_queries():
    bm25 = BM25Index()
    bm25.fit(["휴가 규정 안내", "인사 규정 안내"])

    assert bm25.search("휴가규정", top_k=5)[0][0] == 0
    assert bm25.search("휴가를", top_k=5)[0][0] == 0
    assert bm25.search("인사규정", top_k=5)[0][0] == 1


def test_search_vector_expands_beyond_default_fetch_cap_when_filters_are_active():
    qa = RegulationQASystem()
    docs = []
    qa.documents = []
    qa.doc_meta = []
    qa.doc_ids = []
    qa.doc_index_by_id = {}
    qa.doc_search_fields = []
    for idx in range(200):
        ext = ".pdf" if idx < 150 else ".txt"
        source = f"file{idx}{ext}"
        path = f"C:/docs/{source}"
        doc_id = f"doc#{idx}"
        meta = {"id": doc_id, "file_key": source, "chunk_idx": 0, "source": source, "path": path, "mtime": float(idx)}
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

    results, fetch_k, filtered_out, limit_reached = qa._search_vector("규정", 1, {"extension": ".txt", "filename": "", "path": ""})

    assert qa.vector_store.calls == [20, 40, 80, 160]
    assert fetch_k == 160
    assert len(results) >= 1
    assert filtered_out > 0
    assert limit_reached is False


def test_search_vector_reports_filtered_fetch_limit_reached():
    qa = RegulationQASystem()
    docs = []
    qa.documents = []
    qa.doc_meta = []
    qa.doc_ids = []
    qa.doc_index_by_id = {}
    qa.doc_search_fields = []
    for idx in range(1200):
        source = f"file{idx}.pdf"
        path = f"C:/docs/{source}"
        doc_id = f"doc#{idx}"
        meta = {"id": doc_id, "file_key": source, "chunk_idx": 0, "source": source, "path": path, "mtime": float(idx)}
        docs.append(SimpleNamespace(page_content=f"content {idx}", metadata=meta))
        qa.documents.append(f"content {idx}")
        qa.doc_meta.append(meta)
        qa.doc_ids.append(doc_id)
        qa.doc_index_by_id[doc_id] = idx
        qa.doc_search_fields.append({"source": source.lower(), "path": path.lower(), "extension": ".pdf"})

    class _SearchVectorStore(_FakeVectorStore):
        def similarity_search_with_score(self, query: str, k: int):
            self.calls.append(k)
            return [(docs[idx], float(idx)) for idx in range(min(k, len(docs)))]

    qa.vector_store = _SearchVectorStore()

    results, fetch_k, filtered_out, limit_reached = qa._search_vector("규정", 1, {"extension": ".txt", "filename": "", "path": ""})

    assert results == []
    assert fetch_k == AppConfig.MAX_FILTERED_VECTOR_FETCH
    assert filtered_out == AppConfig.MAX_FILTERED_VECTOR_FETCH
    assert limit_reached is True


def test_bm25_candidates_expand_until_distinct_files_are_available():
    qa = RegulationQASystem()
    qa.documents = ["휴가 규정"] * 61
    qa.doc_meta = []
    qa.doc_ids = []
    qa.doc_index_by_id = {}
    qa.doc_search_fields = []
    for idx in range(61):
        file_key = "same.pdf" if idx < 60 else "other.pdf"
        doc_id = f"{file_key}#{idx}"
        meta = {"id": doc_id, "file_key": file_key, "chunk_idx": idx, "source": file_key, "path": f"C:/docs/{file_key}", "mtime": 1.0}
        qa.doc_meta.append(meta)
        qa.doc_ids.append(doc_id)
        qa.doc_index_by_id[doc_id] = idx
        qa.doc_search_fields.append({"source": file_key, "path": f"c:/docs/{file_key}", "extension": ".pdf"})
    qa._build_bm25()

    results, _ = qa._calculate_hybrid_results(
        "휴가 규정",
        [],
        2,
        "bm25_only",
        {"extension": "", "filename": "", "path": ""},
    )

    assert {item["file_key"] for item in results} == {"same.pdf", "other.pdf"}


def test_calculate_hybrid_results_groups_chunks_by_file():
    qa = RegulationQASystem()
    qa.documents = ["휴가 규정 본문 1", "휴가 규정 본문 2", "인사 규정 본문"]
    qa.doc_meta = [
        {"id": "휴가#0", "file_key": "휴가.pdf", "chunk_idx": 0, "source": "휴가.pdf", "path": "C:/docs/휴가.pdf", "mtime": 1.0},
        {"id": "휴가#1", "file_key": "휴가.pdf", "chunk_idx": 1, "source": "휴가.pdf", "path": "C:/docs/휴가.pdf", "mtime": 1.0},
        {"id": "인사#0", "file_key": "인사.pdf", "chunk_idx": 0, "source": "인사.pdf", "path": "C:/docs/인사.pdf", "mtime": 2.0},
    ]
    qa.doc_ids = ["휴가#0", "휴가#1", "인사#0"]
    qa.doc_index_by_id = {doc_id: idx for idx, doc_id in enumerate(qa.doc_ids)}
    qa.doc_search_fields = [
        {"source": "휴가 pdf", "path": "c:/docs/휴가.pdf", "extension": ".pdf"},
        {"source": "휴가 pdf", "path": "c:/docs/휴가.pdf", "extension": ".pdf"},
        {"source": "인사 pdf", "path": "c:/docs/인사.pdf", "extension": ".pdf"},
    ]

    vec_results = [
        (SimpleNamespace(page_content=qa.documents[0], metadata=qa.doc_meta[0]), 0.1),
        (SimpleNamespace(page_content=qa.documents[1], metadata=qa.doc_meta[1]), 0.2),
        (SimpleNamespace(page_content=qa.documents[2], metadata=qa.doc_meta[2]), 0.3),
    ]

    combined, _ = qa._calculate_hybrid_results("휴가 규정", vec_results, 6, "vector_only", {"extension": "", "filename": "", "path": ""})

    assert len(combined) == 2
    assert combined[0]["file_key"] == "휴가.pdf"
    assert combined[0]["match_count"] == 2
    assert combined[0]["snippet_chunk_idx"] == 0


def test_process_documents_returns_partial_success_when_vector_build_fails(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    fp = folder / "sample.txt"
    fp.write_text("휴가규정 본문", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.embedding_model = object()
    qa.model_id = "demo/model-a"

    class _FakeExtractor:
        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            return "휴가 규정 본문", None

    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", lambda self, cancel_check=None: False)
    qa.extractor = cast(Any, _FakeExtractor())

    discovered_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    process_result = qa.process_documents(str(folder), discovered_files, lambda *_: None)

    assert process_result.success is True
    assert process_result.data["vector_ready"] is False
    assert process_result.data["search_mode"] == "bm25_only"

    search_result = qa.search("휴가규정", k=3, hybrid=True)

    assert search_result.success is True
    assert qa.last_search_stats.search_mode == "bm25_only"
    assert search_result.data[0]["score"] == search_result.data[0]["bm25_score"]


def test_process_documents_drops_stale_cache_when_modified_file_reextract_fails(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    stale_fp = folder / "sample.txt"
    stable_fp = folder / "other.txt"
    stale_fp.write_text("old content", encoding="utf-8")
    stable_fp.write_text("other content", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.embedding_model = object()
    qa.model_id = "demo/model-a"

    class _SwitchingExtractor:
        fail_modified = False

        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            if self.fail_modified and path == str(stale_fp):
                return "", "forced fail"
            return Path(path).read_text(encoding="utf-8"), None

    extractor = _SwitchingExtractor()
    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", lambda self, cancel_check=None: False)
    qa.extractor = cast(Any, extractor)

    discovered_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    first_result = qa.process_documents(str(folder), discovered_files, lambda *_: None)
    assert first_result.success is True

    stale_fp.write_text("new content", encoding="utf-8")
    extractor.fail_modified = True
    updated_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    second_result = qa.process_documents(str(folder), updated_files, lambda *_: None)

    stale_search = qa.search("old", k=5, hybrid=True)
    stable_search = qa.search("other", k=5, hybrid=True)

    assert second_result.success is True
    assert any("sample.txt (forced fail)" in item for item in second_result.failed_items)
    assert stale_search.success is True
    assert stale_search.data == []
    assert stable_search.success is True
    assert stable_search.data[0]["source"] == "other.txt"


def test_process_documents_restores_previous_index_when_canceled(monkeypatch, tmp_path):
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    first_folder.mkdir()
    second_folder.mkdir()
    (first_folder / "first.txt").write_text("첫 번째 규정", encoding="utf-8")
    (second_folder / "second.txt").write_text("두 번째 규정", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.embedding_model = object()
    qa.model_id = "demo/model-a"

    cancel_state = {"flag": False}

    class _CancelableExtractor:
        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            if path.endswith("second.txt"):
                cancel_state["flag"] = True
            return Path(path).read_text(encoding="utf-8"), None

    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", lambda self, cancel_check=None: False)
    qa.extractor = cast(Any, _CancelableExtractor())

    first_files = FileUtils.discover_files(
        str(first_folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    first_result = qa.process_documents(str(first_folder), first_files, lambda *_: None)
    assert first_result.success is True

    before_documents = list(qa.documents)
    before_file_paths = sorted(qa.file_infos.keys())
    before_folder_path = qa.current_folder
    before_search_mode = qa.get_search_mode(True)

    second_files = FileUtils.discover_files(
        str(second_folder),
        recursive=False,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    canceled = qa.process_documents(
        str(second_folder),
        second_files,
        lambda *_: None,
        cancel_check=lambda: cancel_state["flag"],
    )

    assert canceled.success is False
    assert canceled.error_code == "DOCS_CANCELED"
    assert qa.current_folder == before_folder_path
    assert qa.documents == before_documents
    assert sorted(qa.file_infos.keys()) == before_file_paths
    assert qa.get_search_mode(True) == before_search_mode


def test_process_documents_restores_previous_index_when_vector_sync_canceled(monkeypatch, tmp_path):
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    first_folder.mkdir()
    second_folder.mkdir()
    (first_folder / "first.txt").write_text("첫 번째 규정", encoding="utf-8")
    (second_folder / "second.txt").write_text("두 번째 규정", encoding="utf-8")

    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    qa.embedding_model = object()
    qa.model_id = "demo/model-a"

    class _FakeExtractor:
        def extract(self, path: str, pdf_password=None, ocr_engine=None):
            return Path(path).read_text(encoding="utf-8"), None

    def fake_build_first(self, cancel_check=None):
        self.vector_store = _FakeVectorStore()
        return True

    monkeypatch.setattr(RegulationQASystem, "_import_text_splitter", lambda self: _FakeSplitter)
    monkeypatch.setattr(RegulationQASystem, "_import_document_class", lambda self: _FakeDocument)
    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", fake_build_first)
    qa.extractor = cast(Any, _FakeExtractor())

    first_files = FileUtils.discover_files(str(first_folder), recursive=False, supported_extensions=AppConfig.SUPPORTED_EXTENSIONS)
    assert qa.process_documents(str(first_folder), first_files, lambda *_: None).success is True
    before_documents = list(qa.documents)
    before_folder = qa.current_folder

    cancel_state = {"flag": False}

    def fake_build_canceled(self, cancel_check=None):
        cancel_state["flag"] = True
        from regfinder.qa_system import IndexingCanceled

        raise IndexingCanceled()

    monkeypatch.setattr(RegulationQASystem, "_build_vector_store_from_memory", fake_build_canceled)
    second_files = FileUtils.discover_files(str(second_folder), recursive=False, supported_extensions=AppConfig.SUPPORTED_EXTENSIONS)
    canceled = qa.process_documents(str(second_folder), second_files, lambda *_: None, cancel_check=lambda: cancel_state["flag"])

    assert canceled.success is False
    assert canceled.error_code == "DOCS_CANCELED"
    assert qa.current_folder == before_folder
    assert qa.documents == before_documents


def test_search_scores_do_not_use_vector_or_bm25_weight_ceiling():
    qa = RegulationQASystem()
    qa.documents = ["휴가 규정 본문"]
    qa.doc_meta = [{"id": "doc#0", "file_key": "휴가.pdf", "chunk_idx": 0, "source": "휴가.pdf", "path": "C:/docs/휴가.pdf", "mtime": 1.0}]
    qa.doc_ids = ["doc#0"]
    qa.doc_index_by_id = {"doc#0": 0}
    qa.doc_search_fields = [{"source": "휴가 pdf", "path": "c:/docs/휴가.pdf", "extension": ".pdf"}]

    vec_combined, _ = qa._calculate_hybrid_results(
        "휴가",
        [(SimpleNamespace(page_content="휴가 규정 본문", metadata=qa.doc_meta[0]), 3.0)],
        3,
        "vector_only",
        {"extension": "", "filename": "", "path": ""},
    )
    assert vec_combined[0]["score"] == vec_combined[0]["vec_score"]
    assert vec_combined[0]["score"] < 0.7

    qa._build_bm25()
    qa.vector_store = None
    search_result = qa.search("휴가규정", k=3, hybrid=False)

    assert search_result.success is True
    assert search_result.data[0]["score"] == search_result.data[0]["bm25_score"]
    assert search_result.data[0]["score"] > 0.3
