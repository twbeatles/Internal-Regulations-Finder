# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from .app_types import AppConfig, TaskResult
from .file_utils import FileUtils
from .runtime import get_data_directory, get_models_directory
from .ui_style import ui_font

if TYPE_CHECKING:
    from .main_window import MainWindow


def _as_window(instance: object) -> MainWindow:
    return cast("MainWindow", instance)


class MainWindowConfigMixin:
    def _on_font_size_changed(self, value: int) -> None:
        self = _as_window(self)
        self.font_size = value
        self.font_size_label.setText(f"{value}pt")
        self._save_config()

    def _load_config(self) -> None:
        self = _as_window(self)
        cfg = self.config_manager.load()
        self.last_folder = cfg.get("folder", "")
        self.model_name = cfg.get("model", AppConfig.DEFAULT_MODEL)
        self.font_size = cfg.get("font", AppConfig.DEFAULT_FONT_SIZE)
        self.hybrid = bool(cfg.get("hybrid", True))
        self.recursive = bool(cfg.get("recursive", False))
        self.keep_search_text = bool(cfg.get("keep_search_text", True))
        self.sort_by = str(cfg.get("sort_by", "score_desc") or "score_desc")
        self.search_filters = dict(cfg.get("filters", {}) or {"extension": "", "filename": "", "path": ""})
        cfg_recents = cfg.get("recent_folders", [])
        if isinstance(cfg_recents, list) and cfg_recents and not self.recents.get():
            for folder in reversed(cfg_recents):
                if isinstance(folder, str) and folder:
                    self.recents.add(folder)

    def _reset_to_defaults(self) -> None:
        self = _as_window(self)
        self.last_folder = ""
        self.model_name = AppConfig.DEFAULT_MODEL
        self.font_size = AppConfig.DEFAULT_FONT_SIZE
        self.hybrid = True
        self.recursive = False
        self.keep_search_text = True
        self.sort_by = "score_desc"
        self.search_filters = {"extension": "", "filename": "", "path": ""}

    def _save_config(self) -> None:
        self = _as_window(self)
        cfg = {
            "folder": self.last_folder,
            "recent_folders": self.recents.get(),
            "model": self.model_name,
            "font": self.font_size,
            "hybrid": self.hybrid,
            "recursive": self.recursive,
            "keep_search_text": self.keep_search_text,
            "sort_by": self.sort_combo.currentData() if hasattr(self, "sort_combo") else self.sort_by,
            "filters": self._gather_search_filters() if hasattr(self, "ext_filter_combo") else self.search_filters,
        }
        self.config_manager.save(cfg)

    def _gather_search_filters(self) -> dict[str, str]:
        self = _as_window(self)
        return {
            "extension": self.ext_filter_combo.currentData() if hasattr(self, "ext_filter_combo") else "",
            "filename": self.filename_filter_input.text().strip() if hasattr(self, "filename_filter_input") else "",
            "path": self.path_filter_input.text().strip() if hasattr(self, "path_filter_input") else "",
        }


class MainWindowInsightsMixin:
    def _create_bookmarks_view(self) -> QWidget:
        self = _as_window(self)
        view = QWidget()
        view.setObjectName("bookmarksView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        top = QFrame()
        top.setObjectName("card")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 10, 12, 10)

        self.bookmark_count_label = QLabel("⭐ 북마크 0개")
        self.bookmark_count_label.setFont(ui_font(12, QFont.Weight.Bold))
        top_layout.addWidget(self.bookmark_count_label)
        top_layout.addStretch()

        export_btn = QPushButton("📥 내보내기")
        export_btn.clicked.connect(self._export_bookmarks)
        top_layout.addWidget(export_btn)

        remove_btn = QPushButton("🗑️ 선택 삭제")
        remove_btn.clicked.connect(self._remove_selected_bookmark)
        top_layout.addWidget(remove_btn)

        clear_btn = QPushButton("🧹 전체 삭제")
        clear_btn.clicked.connect(self._clear_bookmarks)
        top_layout.addWidget(clear_btn)

        layout.addWidget(top)

        self.bookmark_table = QTableWidget()
        self.bookmark_table.setColumnCount(4)
        self.bookmark_table.setHorizontalHeaderLabels(["시간", "검색어", "파일", "랭킹 점수"])
        header = self.bookmark_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.bookmark_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bookmark_table.setSortingEnabled(True)
        self.bookmark_table.doubleClicked.connect(self._open_selected_bookmark_file)
        layout.addWidget(self.bookmark_table, 1)

        self._refresh_bookmarks_table()
        return view

    def _create_diagnostics_view(self) -> QWidget:
        self = _as_window(self)
        view = QWidget()
        view.setObjectName("diagnosticsView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        top = QFrame()
        top.setObjectName("card")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 10, 12, 10)

        self.diag_summary_label = QLabel("🧰 인덱스/로그 상태")
        self.diag_summary_label.setFont(ui_font(12, QFont.Weight.Bold))
        top_layout.addWidget(self.diag_summary_label)
        top_layout.addStretch()

        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.clicked.connect(self._refresh_diagnostics_view)
        top_layout.addWidget(refresh_btn)

        export_btn = QPushButton("📦 진단 ZIP")
        export_btn.clicked.connect(self._export_diagnostics)
        top_layout.addWidget(export_btn)
        layout.addWidget(top)

        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        layout.addWidget(self.diagnostics_text, 1)
        return view

    def _add_bookmark(self, item: dict[str, Any]) -> None:
        self = _as_window(self)
        query = getattr(self, "last_search_query", self.search_input.text().strip())
        self.bookmarks.add(query, item)
        self._refresh_bookmarks_table()
        self._show_status("⭐ 북마크 저장 완료", "#10b981", 1500)

    def _refresh_bookmarks_table(self) -> None:
        self = _as_window(self)
        if not hasattr(self, "bookmark_table"):
            return
        rows = list(self.bookmarks.items)
        self.bookmark_table.setSortingEnabled(False)
        self.bookmark_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            ts_item = QTableWidgetItem(str(item.get("ts", "")))
            ts_item.setData(Qt.ItemDataRole.UserRole, i)
            self.bookmark_table.setItem(i, 0, ts_item)

            query_item = QTableWidgetItem(str(item.get("query", "")))
            self.bookmark_table.setItem(i, 1, query_item)

            source_item = QTableWidgetItem(str(item.get("source", "")))
            source_item.setToolTip(str(item.get("path", "")))
            source_item.setData(Qt.ItemDataRole.UserRole, str(item.get("path", "")))
            self.bookmark_table.setItem(i, 2, source_item)

            score_item = QTableWidgetItem(f"{float(item.get('score', 0) or 0):.2f}")
            self.bookmark_table.setItem(i, 3, score_item)

        self.bookmark_table.setSortingEnabled(True)
        if hasattr(self, "bookmark_count_label"):
            self.bookmark_count_label.setText(f"⭐ 북마크 {len(rows)}개")

    def _open_selected_bookmark_file(self) -> None:
        self = _as_window(self)
        row = self.bookmark_table.currentRow() if hasattr(self, "bookmark_table") else -1
        if row < 0:
            return
        source_item = self.bookmark_table.item(row, 2)
        if not source_item:
            return
        file_path = source_item.data(Qt.ItemDataRole.UserRole)
        if file_path and os.path.exists(file_path):
            FileUtils.open_file(file_path)

    def _remove_selected_bookmark(self) -> None:
        self = _as_window(self)
        if not hasattr(self, "bookmark_table"):
            return
        row = self.bookmark_table.currentRow()
        if row < 0:
            return
        ts_item = self.bookmark_table.item(row, 0)
        if not ts_item:
            return
        idx = ts_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int):
            self.bookmarks.remove(idx)
            self._refresh_bookmarks_table()
            self._schedule_diagnostics_refresh()

    def _clear_bookmarks(self) -> None:
        self = _as_window(self)
        if QMessageBox.question(self, "확인", "북마크를 모두 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.bookmarks.clear()
            self._refresh_bookmarks_table()
            self._schedule_diagnostics_refresh()
            self._show_status("✅ 북마크 삭제됨", "#10b981", 2000)

    def _write_bookmarks_export_file(self, file_path: str) -> None:
        self = _as_window(self)
        is_csv = file_path.lower().endswith(".csv")
        if is_csv:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["시간", "검색어", "파일", "랭킹 점수", "내용"])
                for item in self.bookmarks.items:
                    score_value = max(0, min(100, int(round(float(item.get("score", 0) or 0) * 100))))
                    writer.writerow([
                        str(item.get("ts", "") or ""),
                        str(item.get("query", "") or ""),
                        str(item.get("source", "") or ""),
                        score_value,
                        str(item.get("content", "") or "").replace("\n", " "),
                    ])
            return

        with open(file_path, "w", encoding="utf-8") as f:
            for i, item in enumerate(self.bookmarks.items, 1):
                score_value = max(0, min(100, int(round(float(item.get("score", 0) or 0) * 100))))
                f.write(f"[{i}] {item.get('ts', '')}\n")
                f.write(f"검색어: {item.get('query', '')}\n")
                f.write(f"파일: {item.get('source', '')}\n")
                f.write(f"랭킹 점수: {score_value}\n")
                f.write(f"내용: {item.get('content', '')}\n")
                f.write("-" * 50 + "\n")

    def _export_bookmarks(self) -> None:
        self = _as_window(self)
        if not self.bookmarks.items:
            QMessageBox.information(self, "알림", "내보낼 북마크가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "북마크 내보내기",
            f"북마크_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV 파일 (*.csv);;텍스트 파일 (*.txt)",
        )
        if not file_path:
            return
        is_csv = file_path.lower().endswith(".csv")
        if not is_csv and not file_path.lower().endswith(".txt"):
            file_path += ".csv"
            is_csv = True

        try:
            self._write_bookmarks_export_file(file_path)
            self._show_status(f"✅ 북마크 내보내기 완료: {os.path.basename(file_path)}", "#10b981", 3000)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"북마크 내보내기 실패: {e}")

    def _clear_recent_folders(self) -> None:
        self = _as_window(self)
        if QMessageBox.question(self, "확인", "최근 폴더 목록을 비우시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.recents.clear()
            self.recent_btn.setEnabled(False)
            self._save_config()
            self._schedule_diagnostics_refresh()
            self._show_status("✅ 최근 폴더 삭제됨", "#10b981", 2000)

    def _refresh_diagnostics_view(self) -> None:
        self = _as_window(self)
        if not hasattr(self, "diagnostics_text"):
            return
        diag = self.qa.collect_diagnostics()
        index_status = self.qa.get_index_status(self.last_folder if self.last_folder and os.path.isdir(self.last_folder) else None)
        search_summary = self.search_logs.summary()
        last_search_stats = diag.get("last_search_stats", {}) if isinstance(diag, dict) else {}
        model_inventory = diag.get("model_inventory", {}) if isinstance(diag, dict) else {}

        lines = []
        lines.append("[Index Status]")
        for k in [
            "cache_root",
            "cache_dir",
            "text_cache_path",
            "schema_version",
            "text_cache_revision",
            "vector_meta_revision",
            "cached_files",
            "cached_chunks",
            "vector_loaded",
            "documents",
            "file_infos",
            "model_id",
        ]:
            if k in index_status:
                lines.append(f"- {k}: {index_status.get(k)}")
        if index_status.get("error"):
            lines.append(f"- error: {index_status.get('error')}")

        lines.append("")
        lines.append("[Search Log Summary]")
        lines.append(f"- total: {search_summary.get('total', 0)}")
        lines.append(f"- success_rate: {search_summary.get('success_rate', 0)}%")
        lines.append(f"- avg_elapsed_ms: {search_summary.get('avg_elapsed_ms', 0)}")
        lines.append(f"- avg_result_count: {search_summary.get('avg_result_count', 0)}")
        top_queries = search_summary.get("top_queries", []) or []
        if top_queries:
            lines.append("- top_queries:")
            for item in top_queries:
                lines.append(f"  - {item.get('query')}: {item.get('count')}")

        lines.append("")
        lines.append("[Last Search Stats]")
        if isinstance(last_search_stats, dict) and last_search_stats:
            for k in ["elapsed_ms", "vector_fetch_k", "bm25_candidates", "filtered_out", "result_count", "query_len", "search_mode", "vector_ready"]:
                if k in last_search_stats:
                    lines.append(f"- {k}: {last_search_stats.get(k)}")
        else:
            lines.append("- none")

        lines.append("")
        lines.append("[Last Operation]")
        last_op = diag.get("last_op", {}) if isinstance(diag, dict) else {}
        if isinstance(last_op, dict) and last_op:
            for k, v in last_op.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- none")

        lines.append("")
        lines.append("[Environment]")
        env = diag.get("environment", {}) if isinstance(diag, dict) else {}
        if isinstance(env, dict):
            for k in ["app_name", "app_version", "platform", "python", "data_dir", "models_dir", "logs_dir"]:
                if k in env:
                    lines.append(f"- {k}: {env.get(k)}")

        lines.append("")
        lines.append("[Model Inventory]")
        if isinstance(model_inventory, dict) and model_inventory:
            for name, state in model_inventory.items():
                if not isinstance(state, dict):
                    continue
                status = "done" if state.get("downloaded") else "online"
                size_bytes = int(state.get("size_bytes", 0) or 0)
                lines.append(f"- {name}: {status} ({FileUtils.format_size(size_bytes)})")
        else:
            lines.append("- none")

        text = "\n".join(lines)
        self.diag_summary_label.setText(
            f"🧰 인덱스/로그 상태 | 검색 {search_summary.get('total', 0)}회 | 북마크 {len(self.bookmarks.items)}개"
        )
        self.diagnostics_text.setPlainText(text)

    def _update_cache_size_display(self, *, refresh_async: bool = True) -> None:
        self = _as_window(self)
        total_size = self.qa.get_cache_usage_bytes()
        self.cache_size_label.setText(f"💾 캐시 사용량: {FileUtils.format_size(total_size)}")
        if refresh_async:
            self._request_cache_usage_refresh()

    def _update_internal_state_display(self) -> None:
        self = _as_window(self)
        if not hasattr(self, "internal_state_label"):
            return

        data_dir = get_data_directory()
        models_dir = get_models_directory()
        cache_root = self.qa.get_cache_root()

        current_cache_dir = ""
        current_text_cache = ""
        if self.last_folder and os.path.isdir(self.last_folder):
            try:
                current_cache_dir = self.qa.get_cache_dir_for_folder(self.last_folder)
                current_text_cache = self.qa._get_text_cache_path(self.last_folder)
            except Exception:
                current_cache_dir = ""
                current_text_cache = ""

        last_op = self.qa.get_last_operation() or {}
        last_op_id = last_op.get("op_id", "")
        last_op_type = last_op.get("kind", last_op.get("type", ""))
        if "success" in last_op:
            last_op_status = "success" if last_op.get("success") else "failed"
        else:
            last_op_status = str(last_op.get("status", ""))

        lines = [
            f"📌 data dir: {data_dir}",
            f"📌 models dir: {models_dir}",
            f"📌 cache root: {cache_root}",
        ]
        if current_cache_dir:
            lines.append(f"📌 current cache: {current_cache_dir}")
        if current_text_cache:
            lines.append(f"📌 text cache: {current_text_cache}")
            try:
                index_status = self.qa.get_index_status(self.last_folder)
                schema = index_status.get("schema_version", "")
                total_files = index_status.get("cached_files", 0)
                total_chunks = index_status.get("cached_chunks", 0)
                revision = index_status.get("text_cache_revision", 0)
                if schema:
                    lines.append(
                        f"📌 cache schema: v{schema}, rev: {revision}, files: {total_files}, chunks: {total_chunks}"
                    )
                vector_ready = index_status.get("vector_ready")
                bm25_ready = index_status.get("bm25_ready")
                search_mode = index_status.get("search_mode")
                memory_warning = index_status.get("memory_warning")
                if vector_ready is not None:
                    lines.append(f"📌 vector ready: {vector_ready}")
                if bm25_ready is not None:
                    lines.append(f"📌 bm25 ready: {bm25_ready}")
                if search_mode:
                    lines.append(f"📌 search mode: {search_mode}")
                if memory_warning:
                    lines.append("📌 memory warning: large index")
            except Exception:
                pass
        if last_op_id:
            lines.append(f"📌 last op: {last_op_type}/{last_op_status} ({last_op_id})")

        text = "\n".join(lines)
        self.internal_state_label.setText(text)
        self.internal_state_label.setToolTip(text)

    def _show_task_error(
        self,
        title: str,
        result: TaskResult,
        *,
        icon: QMessageBox.Icon = QMessageBox.Icon.Critical,
    ) -> None:
        self = _as_window(self)
        guides = {
            "MODEL_LOAD_FAIL": "가이드: 네트워크/모델 캐시/패키지 설치(torch, langchain_huggingface)를 확인하세요.",
            "MODEL_NOT_LOADED": "가이드: 먼저 모델 로드를 완료한 뒤 다시 시도하세요.",
            "DOC_PROCESS_FAIL": "가이드: 접근 권한, 파일 손상 여부, 지원 확장자를 확인하세요.",
            "DOCS_NOT_LOADED": "가이드: 폴더를 로드해 인덱스를 생성한 뒤 검색하세요.",
            "QUERY_TOO_SHORT": "가이드: 검색어를 2글자 이상 입력하세요.",
            "FAISS_SEARCH_FAIL": "가이드: 캐시를 삭제하고 폴더를 다시 로드하세요.",
            "SEARCH_FAIL": "가이드: 검색어/필터를 바꿔 재시도하고, 반복되면 상세 보기를 공유하세요.",
            "DOWNLOAD_FAIL": "가이드: 인터넷 연결과 디스크 여유 공간을 확인하세요.",
            "DOWNLOAD_PARTIAL_FAIL": "가이드: 실패한 모델만 다시 선택해 재다운로드하세요.",
            "DOWNLOAD_CANCELED": "가이드: onefile(EXE) 환경에서는 현재 모델 다운로드가 끝난 뒤 중단될 수 있습니다.",
            "DIAG_EXPORT_FAIL": "가이드: 저장 경로 권한과 디스크 공간을 확인하세요.",
        }
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)

        summary_lines = [result.message or "작업 실패"]
        if getattr(result, "error_code", ""):
            summary_lines.append(f"(error_code: {result.error_code})")
        if getattr(result, "op_id", ""):
            summary_lines.append(f"(op_id: {result.op_id})")
        guide = guides.get(getattr(result, "error_code", ""))
        if guide:
            summary_lines.append("")
            summary_lines.append(guide)
        msg.setText("\n".join(summary_lines))

        detail_btn = None
        if getattr(result, "debug", ""):
            detail_btn = msg.addButton("상세 보기", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()

        if detail_btn is not None and msg.clickedButton() == detail_btn:
            from .ui_components import DebugDetailsDialog

            details_title = f"{title} 상세"
            dlg = DebugDetailsDialog(details_title, result.debug, self)
            dlg.exec()
