# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton

from regfinder.app_types import FileInfo, FileStatus, TaskResult
from regfinder.file_utils import FileUtils
from regfinder.main_window import MainWindow
from regfinder.qa_system import RegulationQASystem

_APP: QApplication | None = None


def _get_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is not None:
        _APP = cast(QApplication, app)
        return cast(QApplication, app)
    _APP = QApplication([])
    return _APP


def _patch_window_environment(monkeypatch, tmp_path: Path) -> None:
    data_dir = str(tmp_path)
    models_dir = str(tmp_path / "models")
    history_path = str(tmp_path / "search_history.json")
    config_path = str(tmp_path / "config.json")

    monkeypatch.setattr("regfinder.main_window.QTimer.singleShot", lambda *args, **kwargs: None)
    monkeypatch.setattr("regfinder.main_window.MainWindow._request_cache_usage_refresh", lambda self: None)
    monkeypatch.setattr("regfinder.main_window.MainWindow._schedule_diagnostics_refresh", lambda self, delay_ms=120: None)
    monkeypatch.setattr("regfinder.persistence.get_data_directory", lambda: data_dir)
    monkeypatch.setattr("regfinder.persistence.get_config_path", lambda: config_path)
    monkeypatch.setattr("regfinder.runtime.get_data_directory", lambda: data_dir)
    monkeypatch.setattr("regfinder.runtime.get_models_directory", lambda: models_dir)
    monkeypatch.setattr("regfinder.runtime.get_history_path", lambda: history_path)
    monkeypatch.setattr("regfinder.ui_components.get_history_path", lambda: history_path)
    monkeypatch.setattr("regfinder.model_inventory.get_data_directory", lambda: data_dir)
    monkeypatch.setattr("regfinder.model_inventory.get_models_directory", lambda: models_dir)
    monkeypatch.setattr("regfinder.main_window.get_models_directory", lambda: models_dir)
    monkeypatch.setattr("regfinder.main_window_mixins.get_data_directory", lambda: data_dir)
    monkeypatch.setattr("regfinder.main_window_mixins.get_models_directory", lambda: models_dir)


class _Signal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _ImmediateSearchThread:
    def __init__(self, qa, query, k, hybrid, filters=None, sort_by: str = "score_desc"):
        self.qa = qa
        self.query = query
        self.k = k
        self.hybrid = hybrid
        self.filters = filters or {}
        self.sort_by = sort_by
        self.finished = _Signal()
        self.progress = _Signal()
        self._running = False
        self._canceled = False

    def isRunning(self):
        return self._running

    def cancel(self):
        self._canceled = True

    def start(self):
        self._running = True
        result = self.qa.search(
            self.query,
            self.k,
            self.hybrid,
            filters=self.filters,
            sort_by=self.sort_by,
            progress_cb=lambda message: self.progress.emit(str(message)),
            cancel_check=lambda: self._canceled,
        )
        if self._canceled and result.success:
            result = TaskResult(False, "검색이 취소되었습니다", error_code="SEARCH_CANCELED")
        self._running = False
        self.finished.emit(result)

    def deleteLater(self):
        return None


class _DeferredSearchThread:
    last_instance = None

    def __init__(self, qa, query, k, hybrid, filters=None, sort_by: str = "score_desc"):
        self.qa = qa
        self.query = query
        self.k = k
        self.hybrid = hybrid
        self.filters = filters or {}
        self.sort_by = sort_by
        self.finished = _Signal()
        self.progress = _Signal()
        self._running = False
        self._canceled = False
        type(self).last_instance = self

    def isRunning(self):
        return self._running

    def cancel(self):
        self._canceled = True

    def start(self):
        self._running = True
        self.progress.emit("검색 준비 중...")

    def finish(self, result: TaskResult):
        if self._canceled and result.success:
            result = TaskResult(False, "검색이 취소되었습니다", error_code="SEARCH_CANCELED")
        self._running = False
        self.finished.emit(result)

    def deleteLater(self):
        return None


def _make_window(monkeypatch, tmp_path: Path, qa: RegulationQASystem | None = None) -> MainWindow:
    _patch_window_environment(monkeypatch, tmp_path)
    app = _get_app()
    window = MainWindow(qa or RegulationQASystem())
    app.processEvents()
    return window


def test_main_window_allows_bm25_only_search(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"

    def fake_search(query: str, k: int = 3, hybrid: bool = True, **kwargs):
        qa.last_search_stats.search_mode = "bm25_only"
        return TaskResult(
            True,
            "검색 완료",
            [
                {
                    "source": "휴가규정.pdf",
                    "path": r"C:\docs\휴가규정.pdf",
                    "content": "휴가 규정 본문",
                    "score": 0.82,
                    "vec_score": 0.0,
                    "bm25_score": 0.82,
                    "match_count": 1,
                    "snippet_chunk_idx": 0,
                }
            ],
        )

    qa.get_search_mode = lambda hybrid=True: "bm25_only"  # type: ignore[method-assign]
    qa.search = fake_search  # type: ignore[method-assign]

    warnings = []
    monkeypatch.setattr("regfinder.main_window.SearchThread", _ImmediateSearchThread)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args))

    window = _make_window(monkeypatch, tmp_path, qa)
    window._set_search_controls_enabled(True)
    window.search_input.setText("휴가규정")

    window._search()

    assert warnings == []
    assert window.last_search_query == "휴가규정"
    assert len(window.last_search_results) == 1
    assert any(
        isinstance(label, QLabel) and label.text() == '🔎 "휴가규정" - 1개 결과'
        for label in window.result_container.findChildren(QLabel)
    )
    window.close()


def test_prepare_pdf_passwords_prompts_for_encrypted_files(monkeypatch, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    enc_pdf = folder / "enc.pdf"
    plain_pdf = folder / "plain.pdf"
    txt = folder / "note.txt"
    enc_pdf.write_text("x", encoding="utf-8")
    plain_pdf.write_text("x", encoding="utf-8")
    txt.write_text("x", encoding="utf-8")

    qa = RegulationQASystem()

    def fake_check(path: str):
        return (path.endswith("enc.pdf"), None)

    qa.extractor.check_pdf_encrypted = fake_check  # type: ignore[method-assign]

    dialog_payload = {}

    class _FakePasswordDialog:
        def __init__(self, files, parent=None):
            dialog_payload["files"] = files

        def exec(self):
            return QDialog.DialogCode.Accepted

        def passwords(self):
            return {str(enc_pdf): "secret", str(plain_pdf): ""}

    monkeypatch.setattr("regfinder.main_window.PdfPasswordDialog", _FakePasswordDialog)

    window = _make_window(monkeypatch, tmp_path, qa)
    discovered_files = FileUtils.discover_files(
        str(folder),
        recursive=False,
        supported_extensions=(".txt", ".pdf"),
    )

    passwords = window._prepare_pdf_passwords(discovered_files)

    assert passwords == {str(enc_pdf): "secret"}
    assert window.pdf_passwords == {str(enc_pdf): "secret"}
    assert [item["label"] for item in dialog_payload["files"]] == ["enc.pdf"]
    window.close()


def test_results_and_bookmarks_export_use_csv_writer(monkeypatch, tmp_path):
    window = _make_window(monkeypatch, tmp_path)
    window.last_search_query = '쉼표,"검색"'
    window.last_search_results = [
        {
            "source": '규정,"휴가".pdf',
            "path": r"C:\docs\규정.pdf",
            "content": '줄1\n줄2, "quoted"',
            "score": 0.82,
            "match_count": 2,
        }
    ]
    window.bookmarks.items = [
        {
            "ts": "2026-03-19T10:00:00",
            "query": '쉼표,"검색"',
            "source": '규정,"휴가".pdf',
            "content": '줄1\n줄2, "quoted"',
            "score": 0.71,
        }
    ]

    results_csv = tmp_path / "results.csv"
    bookmarks_csv = tmp_path / "bookmarks.csv"
    window._write_results_export_file(str(results_csv))
    window._write_bookmarks_export_file(str(bookmarks_csv))

    with open(results_csv, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    with open(bookmarks_csv, "r", encoding="utf-8", newline="") as f:
        bookmark_rows = list(csv.reader(f))

    assert rows[1][2] == '규정,"휴가".pdf'
    assert rows[1][4] == '줄1 줄2, "quoted"'
    assert bookmark_rows[1][1] == '쉼표,"검색"'
    assert bookmark_rows[1][2] == '규정,"휴가".pdf'
    assert bookmark_rows[1][4] == '줄1 줄2, "quoted"'
    window.close()


def test_clear_cache_resets_ui_and_session_passwords(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: ""  # type: ignore[method-assign]
    qa.file_infos[str(tmp_path / "sample.txt")] = FileInfo(
        path=str(tmp_path / "sample.txt"),
        name="sample.txt",
        extension=".txt",
        size=10,
        status=FileStatus.SUCCESS,
        chunks=2,
    )

    window = _make_window(monkeypatch, tmp_path, qa)
    window.last_folder = str(tmp_path)
    window.pdf_passwords = {str(tmp_path / "secret.pdf"): "secret"}
    window.last_search_results = [{"source": "sample.txt", "content": "본문", "score": 0.8, "match_count": 1}]
    window.last_search_query = "본문"
    window._update_file_table()
    window._clear_results()
    window.result_layout.addWidget(QLabel("stale-result"))

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    window._clear_cache()

    assert window.file_table.rowCount() == 0
    assert window.last_search_results == []
    assert window.last_search_query == ""
    assert window.pdf_passwords == {}
    assert window.search_input.isEnabled() is False
    assert window.refresh_btn.isEnabled() is True
    assert any(
        isinstance(label, QLabel) and label.text() == "사내 규정 검색기"
        for label in window.result_container.findChildren(QLabel)
    )
    window.close()


def test_model_only_state_disables_search_panel(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: ""  # type: ignore[method-assign]

    window = _make_window(monkeypatch, tmp_path, qa)

    assert window.folder_btn.isEnabled() is True
    assert window.search_input.isEnabled() is False
    assert window.search_btn.isEnabled() is False
    assert window.history_btn.isEnabled() is False
    assert window.sort_combo.isEnabled() is False
    window.close()


def test_search_keeps_previous_results_and_shows_inline_progress(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: "bm25_only"  # type: ignore[method-assign]
    monkeypatch.setattr("regfinder.main_window.SearchThread", _DeferredSearchThread)

    window = _make_window(monkeypatch, tmp_path, qa)
    window._render_search_results(
        query="이전 검색",
        results=[
            {
                "source": "이전결과.txt",
                "path": str(tmp_path / "old.txt"),
                "content": "이전 결과 본문",
                "score": 0.7,
                "vec_score": 0.0,
                "bm25_score": 0.7,
                "match_count": 1,
                "snippet_chunk_idx": 0,
                "file_key": "old-file",
                "matched_chunk_indices": [0],
            }
        ],
        elapsed_ms=120,
        search_mode="bm25_only",
        filters={"extension": "", "filename": "", "path": ""},
        sort_by="score_desc",
    )

    window.search_input.setText("새 검색")
    window.filename_filter_input.setText("규정")
    window._search()

    app = _get_app()
    app.processEvents()

    assert any(
        isinstance(label, QLabel) and label.text() == '🔎 "이전 검색" - 1개 결과'
        for label in window.result_container.findChildren(QLabel)
    )
    assert window.search_input.isEnabled() is False
    assert window.history_btn.isEnabled() is False
    assert window._search_progress_card is not None

    worker = _DeferredSearchThread.last_instance
    assert worker is not None
    worker.finish(
        TaskResult(
            True,
            "검색 완료",
            [
                {
                    "source": "신규결과.txt",
                    "path": str(tmp_path / "new.txt"),
                    "content": "새 검색 결과 본문",
                    "score": 0.91,
                    "vec_score": 0.0,
                    "bm25_score": 0.91,
                    "match_count": 2,
                    "snippet_chunk_idx": 1,
                    "file_key": "new-file",
                    "matched_chunk_indices": [1, 3],
                }
            ],
        )
    )
    app.processEvents()

    assert window._search_progress_card is None
    assert window.search_input.isEnabled() is True
    assert any(
        isinstance(label, QLabel) and label.text() == '🔎 "새 검색" - 1개 결과'
        for label in window.result_container.findChildren(QLabel)
    )
    window.close()


def test_no_results_with_filters_offer_reset_action(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: "bm25_only"  # type: ignore[method-assign]
    qa.search = lambda query, k=3, hybrid=True, **kwargs: TaskResult(True, "검색 완료", [])  # type: ignore[method-assign]
    monkeypatch.setattr("regfinder.main_window.SearchThread", _ImmediateSearchThread)

    window = _make_window(monkeypatch, tmp_path, qa)
    window.search_input.setText("없는검색")
    window.filename_filter_input.setText("휴가")
    window.path_filter_input.setText("hr/policy")
    window.ext_filter_combo.setCurrentIndex(window.ext_filter_combo.findData(".pdf"))

    window._search()

    labels = [label.text() for label in window.result_container.findChildren(QLabel)]
    buttons = [button.text() for button in window.result_container.findChildren(QPushButton)]
    assert any("현재 필터: 형식=.pdf / 파일명=휴가 / 경로=hr/policy" == text for text in labels)
    assert "필터 초기화" in buttons
    window.close()


def test_search_history_restores_conditions_and_researches(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: "hybrid" if hybrid else "bm25_only"  # type: ignore[method-assign]
    captured = {}

    def fake_search(query: str, k: int = 3, hybrid: bool = True, **kwargs):
        captured["query"] = query
        captured["k"] = k
        captured["hybrid"] = hybrid
        captured["filters"] = kwargs.get("filters")
        captured["sort_by"] = kwargs.get("sort_by")
        qa.last_search_stats.search_mode = "hybrid" if hybrid else "bm25_only"
        return TaskResult(True, "검색 완료", [])

    qa.search = fake_search  # type: ignore[method-assign]
    monkeypatch.setattr("regfinder.main_window.SearchThread", _ImmediateSearchThread)

    window = _make_window(monkeypatch, tmp_path, qa)
    window._search_from_history(
        {
            "q": "휴가",
            "filters": {"extension": ".pdf", "filename": "규정", "path": "hr"},
            "sort_by": "mtime_desc",
            "k": 5,
            "hybrid": False,
        }
    )

    assert window.search_input.text() == "휴가"
    assert window.filename_filter_input.text() == "규정"
    assert window.path_filter_input.text() == "hr"
    assert window.k_spin.value() == 5
    assert captured == {
        "query": "휴가",
        "k": 5,
        "hybrid": False,
        "filters": {"extension": ".pdf", "filename": "규정", "path": "hr"},
        "sort_by": "mtime_desc",
    }
    window.close()


def test_busy_guard_blocks_clear_cache_during_search(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.get_search_mode = lambda hybrid=True: "bm25_only"  # type: ignore[method-assign]
    called = {"clear_cache": 0, "info": 0}

    class _BusyWorker:
        def isRunning(self):
            return True

        def cancel(self):
            return None

    def fake_clear_cache():
        called["clear_cache"] += 1

    monkeypatch.setattr(qa, "clear_cache", fake_clear_cache)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: called.__setitem__("info", called["info"] + 1))

    window = _make_window(monkeypatch, tmp_path, qa)
    window.workers.set("search", _BusyWorker())
    window._clear_cache()

    assert called["clear_cache"] == 0
    assert called["info"] == 1
    window.close()


def test_file_and_bookmark_tables_sort_numerically(monkeypatch, tmp_path):
    qa = RegulationQASystem()
    qa.embedding_model = object()
    qa.model_id = "demo/model"
    qa.file_infos = {
        "small": FileInfo("small", "작은파일.txt", ".txt", 9, FileStatus.SUCCESS, 10),
        "large": FileInfo("large", "큰파일.txt", ".txt", 100, FileStatus.SUCCESS, 2),
    }

    window = _make_window(monkeypatch, tmp_path, qa)
    window._update_file_table()
    window.file_table.sortItems(2)
    _get_app().processEvents()
    assert window.file_table.item(0, 1).text() == "작은파일.txt"

    window.file_table.sortItems(3)
    _get_app().processEvents()
    assert window.file_table.item(0, 1).text() == "큰파일.txt"

    window.bookmarks.items = [
        {"ts": "2026-03-25T10:00:00", "query": "q1", "source": "a", "path": "a", "score": 10.0, "content": "a"},
        {"ts": "2026-03-25T11:00:00", "query": "q2", "source": "b", "path": "b", "score": 2.0, "content": "b"},
    ]
    window._refresh_bookmarks_table()
    window.bookmark_table.sortItems(3)
    _get_app().processEvents()
    assert window.bookmark_table.item(0, 2).text() == "b"
    window.close()
