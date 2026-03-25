# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .app_types import AppConfig, SearchHistoryEntry
from .file_utils import FileUtils
from .runtime import get_history_path, logger
from .search_text import highlight_spans
from .ui_style import ui_font


def _apply_highlight(text_edit: QTextEdit, content: str, query: str) -> None:
    text_edit.setPlainText(content)

    if not query or len(query) < 2:
        return

    highlight_format = QTextCharFormat()
    highlight_format.setBackground(QColor("#e94560"))
    highlight_format.setForeground(QColor("white"))

    cursor = text_edit.textCursor()
    for start, end in highlight_spans(content, query):
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(highlight_format)

    cursor.setPosition(0)
    text_edit.setTextCursor(cursor)


class SearchHistory:
    def __init__(self):
        self.items: List[SearchHistoryEntry] = []
        self.path = get_history_path()
        self._load()

    def _normalize_item(self, raw: Any) -> SearchHistoryEntry | None:
        if isinstance(raw, dict):
            query = str(raw.get("q", "") or "").strip()
            if not query:
                return None
            filters = raw.get("filters", {})
            filters_dict = {
                "extension": "",
                "filename": "",
                "path": "",
            }
            if isinstance(filters, dict):
                filters_dict.update(
                    {
                        "extension": str(filters.get("extension", "") or ""),
                        "filename": str(filters.get("filename", "") or ""),
                        "path": str(filters.get("path", "") or ""),
                    }
                )
            try:
                k = int(raw.get("k", AppConfig.DEFAULT_SEARCH_RESULTS) or AppConfig.DEFAULT_SEARCH_RESULTS)
            except Exception:
                k = AppConfig.DEFAULT_SEARCH_RESULTS
            hybrid_raw = raw.get("hybrid", True)
            hybrid = hybrid_raw if isinstance(hybrid_raw, bool) else str(hybrid_raw).strip().lower() not in {"0", "false", "no", ""}
            return {
                "q": query,
                "filters": filters_dict,
                "sort_by": str(raw.get("sort_by", "score_desc") or "score_desc"),
                "k": int(max(1, min(k, AppConfig.MAX_SEARCH_RESULTS))),
                "hybrid": hybrid,
            }
        if isinstance(raw, str):
            query = raw.strip()
            if not query:
                return None
            return {
                "q": query,
                "filters": {"extension": "", "filename": "", "path": ""},
                "sort_by": "score_desc",
                "k": AppConfig.DEFAULT_SEARCH_RESULTS,
                "hybrid": True,
            }
        return None

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    items: List[SearchHistoryEntry] = []
                    for raw in data[: AppConfig.MAX_HISTORY_SIZE]:
                        entry = self._normalize_item(raw)
                        if entry is not None:
                            items.append(entry)
                    self.items = items
                    return
            except Exception:
                logger.warning(f"히스토리 로드 실패: {self.path}")
        self.items = []

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.items[: AppConfig.MAX_HISTORY_SIZE], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"히스토리 저장 실패: {e}")

    def add(
        self,
        query: str,
        *,
        filters: Dict[str, str] | None = None,
        sort_by: str = "score_desc",
        k: int = AppConfig.DEFAULT_SEARCH_RESULTS,
        hybrid: bool = True,
    ):
        query = str(query or "").strip()
        if not query:
            return
        entry: SearchHistoryEntry = {
            "q": query,
            "filters": {
                "extension": str((filters or {}).get("extension", "") or ""),
                "filename": str((filters or {}).get("filename", "") or ""),
                "path": str((filters or {}).get("path", "") or ""),
            },
            "sort_by": str(sort_by or "score_desc"),
            "k": int(max(1, min(int(k or AppConfig.DEFAULT_SEARCH_RESULTS), AppConfig.MAX_SEARCH_RESULTS))),
            "hybrid": bool(hybrid),
        }
        self.items = [item for item in self.items if item["q"] != query]
        self.items.insert(0, entry)
        self.items = self.items[: AppConfig.MAX_HISTORY_SIZE]
        self._save()

    def get(self, count: int = 10) -> List[SearchHistoryEntry]:
        return list(self.items[:count])

    def clear(self):
        self.items = []
        self._save()


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, numeric_value: float | int):
        super().__init__(text)
        self.numeric_value = float(numeric_value)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, NumericTableWidgetItem):
            return self.numeric_value < other.numeric_value
        try:
            return self.numeric_value < float(other.text())
        except Exception:
            return super().__lt__(other)


class FileLinkLabel(QLabel):
    def __init__(self, text: str, path: str):
        super().__init__(text)
        self._path = path
        self.setToolTip(f"📁 {path}\n클릭하여 파일 열기")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton:
            FileUtils.open_file(self._path)
        super().mousePressEvent(ev)


class SearchProgressCard(QFrame):
    canceled = pyqtSignal()

    def __init__(self, query: str, filter_text: str, sort_text: str):
        super().__init__()
        self.setObjectName("searchProgressCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("🔍 검색 진행 중")
        title.setFont(ui_font(12, QFont.Weight.Bold))
        title_row.addWidget(title)
        title_row.addStretch()
        self.elapsed_label = QLabel("⏱ 0.0초")
        self.elapsed_label.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        title_row.addWidget(self.elapsed_label)
        layout.addLayout(title_row)

        self.query_label = QLabel(f"질의: \"{query}\"")
        self.query_label.setWordWrap(True)
        layout.addWidget(self.query_label)

        self.meta_label = QLabel(f"필터: {filter_text} | 정렬: {sort_text}")
        self.meta_label.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        bottom_row = QHBoxLayout()
        self.status_label = QLabel("검색 준비 중...")
        self.status_label.setStyleSheet("color: #eaeaea;")
        self.status_label.setWordWrap(True)
        bottom_row.addWidget(self.status_label, 1)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setFixedHeight(30)
        self.cancel_btn.clicked.connect(self._on_cancel)
        bottom_row.addWidget(self.cancel_btn)
        layout.addLayout(bottom_row)

    def _on_cancel(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("취소 요청됨")
        self.status_label.setText("검색 취소를 요청했습니다. 현재 단계가 끝나면 중단됩니다.")
        self.canceled.emit()

    def set_status(self, text: str) -> None:
        if text:
            self.status_label.setText(text)

    def set_elapsed_seconds(self, elapsed_seconds: float) -> None:
        self.elapsed_label.setText(f"⏱ {max(0.0, elapsed_seconds):.1f}초")


class ResultCard(QFrame):
    """검색 결과를 표시하는 카드 위젯"""

    def __init__(
        self,
        idx: int,
        data: Dict[str, Any],
        on_copy: Callable[[str], None],
        on_bookmark: Callable[[Dict[str, Any]], None] | None = None,
        font_size: int = 12,
        query: str = "",
        on_details: Callable[[Dict[str, Any]], None] | None = None,
    ):
        super().__init__()
        self.setObjectName("resultCard")
        self.data = data
        self.query = query
        self.on_bookmark = on_bookmark
        self.on_details = on_details

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel(f"{idx}")
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            """
            background: #e94560;
            color: white;
            border-radius: 14px;
            font-weight: bold;
            font-size: 12px;
            """
        )
        header.addWidget(badge)

        source_path = str(data.get("path", ""))
        source: QLabel
        if source_path:
            source = FileLinkLabel(str(data["source"]), source_path)
        else:
            source = QLabel(str(data["source"]))
        source.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        header.addWidget(source)

        header.addStretch()

        score = max(0, min(100, int(round(float(data.get("score", 0) or 0) * 100))))
        vec_score = max(0, min(100, int(round(float(data.get("vec_score", 0) or 0) * 100))))
        bm25_score = max(0, min(100, int(round(float(data.get("bm25_score", 0) or 0) * 100))))
        score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"

        score_container = QHBoxLayout()
        score_container.setSpacing(8)

        pbar = QProgressBar()
        pbar.setFixedWidth(80)
        pbar.setFixedHeight(8)
        pbar.setValue(score)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(
            f"""
            QProgressBar {{ background: #0f3460; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {score_color}; border-radius: 4px; }}
            """
        )
        score_container.addWidget(pbar)

        score_lbl = QLabel(f"랭킹 {score}")
        score_lbl.setStyleSheet(f"color: {score_color}; font-weight: bold; font-size: 13px;")
        score_lbl.setToolTip(f"상대 랭킹 점수: {score}\n벡터: {vec_score} | 키워드: {bm25_score}")
        score_container.addWidget(score_lbl)

        header.addLayout(score_container)

        btn_container = QHBoxLayout()
        btn_container.setSpacing(6)

        copy_btn = QPushButton("📋 복사")
        copy_btn.setFixedHeight(30)
        copy_btn.setFixedWidth(75)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: on_copy(str(data.get("content", "") or "")))
        btn_container.addWidget(copy_btn)

        if self.on_bookmark is not None:
            bookmark_handler = self.on_bookmark
            save_btn = QPushButton("⭐ 저장")
            save_btn.setFixedHeight(30)
            save_btn.setFixedWidth(75)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.clicked.connect(lambda: bookmark_handler(data))
            btn_container.addWidget(save_btn)

        if self.on_details is not None:
            detail_handler = self.on_details
            detail_btn = QPushButton("🧾 상세")
            detail_btn.setFixedHeight(30)
            detail_btn.setFixedWidth(75)
            detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            detail_btn.clicked.connect(lambda: detail_handler(data))
            btn_container.addWidget(detail_btn)

        if data.get("path"):
            open_btn = QPushButton("📂 열기")
            open_btn.setFixedHeight(30)
            open_btn.setFixedWidth(75)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda: FileUtils.open_file(str(data["path"])))
            btn_container.addWidget(open_btn)

        header.addLayout(btn_container)
        layout.addLayout(header)

        evidence_count = max(1, int(data.get("match_count", 1) or 1))
        snippet_chunk_idx = int(data.get("snippet_chunk_idx", data.get("chunk_idx", 0)) or 0) + 1
        evidence_label = QLabel(f"근거 청크 {evidence_count}개 | 대표 청크 #{snippet_chunk_idx}")
        evidence_label.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        layout.addWidget(evidence_label)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setMinimumHeight(80)
        self.content.setMaximumHeight(180)
        self.set_font_size(font_size)
        _apply_highlight(self.content, str(data.get("content", "") or ""), query)
        layout.addWidget(self.content)

    def set_font_size(self, font_size: int) -> None:
        self.content.setFont(ui_font(font_size))


class EmptyStateWidget(QFrame):
    """빈 상태를 표시하는 위젯"""

    def __init__(
        self,
        icon: str = "📂",
        title: str = "",
        description: str = "",
        *,
        details: Sequence[str] | None = None,
        action_text: str = "",
        action_callback: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.setObjectName("emptyStateCard")
        self.setMinimumHeight(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel(icon)
        icon_label.setObjectName("emptyStateIcon")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("emptyStateTitle")
            title_label.setFont(ui_font(16, QFont.Weight.Bold))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("emptyStateDescription")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            desc_label.setMaximumWidth(420)
            layout.addWidget(desc_label)

        if details:
            detail_label = QLabel("\n".join(str(item) for item in details if item))
            detail_label.setObjectName("emptyStateDetails")
            detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail_label.setWordWrap(True)
            detail_label.setMaximumWidth(520)
            layout.addWidget(detail_label)

        if action_text and action_callback is not None:
            action_btn = QPushButton(action_text)
            action_btn.setFixedHeight(34)
            action_btn.clicked.connect(action_callback)
            layout.addWidget(action_btn)


class ProgressDialog(QDialog):
    """문서 처리 및 모델 다운로드 진행 상황을 표시하는 모달 다이얼로그"""

    canceled = pyqtSignal()

    def __init__(self, parent=None, title: str = "처리 중"):
        super().__init__(parent)
        self.setObjectName("progressDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 180)
        self._cancel_pending_message = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        self.title_label = QLabel(title)
        self.title_label.setFont(ui_font(14, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.status_label = QLabel("준비 중...")
        self.status_label.setStyleSheet("color: #888;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(12)
        layout.addWidget(self.progress_bar)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: #666; font-size: 11px;")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_label)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet("background: #dc2626;")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

    def _on_cancel(self):
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("취소 중...")
        self.canceled.emit()

    def set_cancel_pending(self, message: str, *, button_text: str = "중단 요청됨"):
        self._cancel_pending_message = str(message or "")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText(button_text)
        if self._cancel_pending_message:
            self.detail_label.setText(self._cancel_pending_message)

    def update_progress(self, percent: int, status: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)
        if self._cancel_pending_message:
            self.detail_label.setText(self._cancel_pending_message)
            return
        self.detail_label.setText(f"{percent}% 완료")


class PdfPasswordDialog(QDialog):
    def __init__(self, files: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("암호화 PDF 비밀번호 입력")
        self.resize(620, 420)
        self._inputs: Dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        info_label = QLabel(
            "암호화된 PDF가 감지되었습니다.\n"
            "파일별 비밀번호를 입력하세요. 비워두면 해당 파일은 이번 인덱스에서 제외됩니다.\n"
            "비밀번호는 현재 앱 세션 메모리에만 유지되며 디스크에 저장하지 않습니다."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(10)
        for item in files:
            path = str(item.get("path", "") or "")
            label = str(item.get("label", path) or path)
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("비워두면 이번 로드에서 건너뜁니다")
            edit.setText(str(item.get("password", "") or ""))
            edit.setClearButtonEnabled(True)
            form.addRow(label, edit)
            self._inputs[path] = edit
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def passwords(self) -> Dict[str, str]:
        return {
            path: edit.text()
            for path, edit in self._inputs.items()
        }


class ResultDetailDialog(QDialog):
    def __init__(
        self,
        result_data: Dict[str, Any],
        chunks: Sequence[Dict[str, Any]],
        *,
        query: str,
        font_size: int,
        parent=None,
    ):
        super().__init__(parent)
        self.result_data = result_data
        self.chunks = sorted(
            [dict(item) for item in chunks],
            key=lambda item: int(item.get("chunk_idx", 0) or 0),
        )
        self.query = query
        self.font_size = font_size
        self._show_full_document = False
        matched = result_data.get("matched_chunk_indices", []) or []
        self.matched_chunk_indices = sorted({int(value) for value in matched})
        if not self.matched_chunk_indices:
            self.matched_chunk_indices = [int(result_data.get("snippet_chunk_idx", 0) or 0)]
        self._matched_position = 0

        source = str(result_data.get("source", "") or "")
        self.setWindowTitle(f"상세 보기 - {source}")
        self.resize(900, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(source)
        title.setFont(ui_font(14, QFont.Weight.Bold))
        layout.addWidget(title)

        path_label = QLabel(str(result_data.get("path", "") or ""))
        path_label.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        summary = QLabel(
            f"랭킹 점수 {max(0, min(100, int(round(float(result_data.get('score', 0) or 0) * 100))))} | "
            f"근거 청크 {max(1, int(result_data.get('match_count', 1) or 1))}개"
        )
        summary.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        layout.addWidget(summary)

        action_row = QHBoxLayout()
        open_btn = QPushButton("📂 파일 열기")
        open_btn.clicked.connect(self._open_file)
        action_row.addWidget(open_btn)
        copy_path_btn = QPushButton("📋 경로 복사")
        copy_path_btn.clicked.connect(self._copy_path)
        action_row.addWidget(copy_path_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        mode_row = QHBoxLayout()
        self.chunk_mode_btn = QPushButton("근거 청크 보기")
        self.chunk_mode_btn.clicked.connect(self._show_chunk_mode)
        mode_row.addWidget(self.chunk_mode_btn)
        self.full_mode_btn = QPushButton("전체 문서 보기")
        self.full_mode_btn.clicked.connect(self._show_full_mode)
        mode_row.addWidget(self.full_mode_btn)
        mode_row.addStretch()
        self.prev_btn = QPushButton("이전 근거")
        self.prev_btn.clicked.connect(lambda: self._move_match(-1))
        mode_row.addWidget(self.prev_btn)
        self.next_btn = QPushButton("다음 근거")
        self.next_btn.clicked.connect(lambda: self._move_match(1))
        mode_row.addWidget(self.next_btn)
        layout.addLayout(mode_row)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(ui_font(font_size))
        layout.addWidget(self.text, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self._update_mode_buttons()
        self._update_view()

    def _open_file(self) -> None:
        path = str(self.result_data.get("path", "") or "")
        if path:
            FileUtils.open_file(path)

    def _copy_path(self) -> None:
        path = str(self.result_data.get("path", "") or "")
        clipboard = QApplication.clipboard()
        if clipboard is not None and path:
            clipboard.setText(path)

    def _show_chunk_mode(self) -> None:
        self._show_full_document = False
        self._update_mode_buttons()
        self._update_view()

    def _show_full_mode(self) -> None:
        self._show_full_document = True
        self._update_mode_buttons()
        self._update_view()

    def _move_match(self, step: int) -> None:
        if not self.matched_chunk_indices:
            return
        self._show_full_document = False
        self._matched_position = (self._matched_position + step) % len(self.matched_chunk_indices)
        self._update_mode_buttons()
        self._update_view()

    def _update_mode_buttons(self) -> None:
        self.chunk_mode_btn.setEnabled(self._show_full_document)
        self.full_mode_btn.setEnabled(not self._show_full_document)
        has_multiple_matches = len(self.matched_chunk_indices) > 1
        self.prev_btn.setEnabled(not self._show_full_document and has_multiple_matches)
        self.next_btn.setEnabled(not self._show_full_document and has_multiple_matches)

    def _current_chunk(self) -> Dict[str, Any] | None:
        if not self.chunks:
            return None
        target_idx = self.matched_chunk_indices[self._matched_position]
        for chunk in self.chunks:
            if int(chunk.get("chunk_idx", 0) or 0) == target_idx:
                return chunk
        return self.chunks[0]

    def _update_view(self) -> None:
        if self._show_full_document:
            content = "\n\n".join(str(chunk.get("content", "") or "") for chunk in self.chunks)
            if not content:
                content = str(self.result_data.get("content", "") or "")
            self.info_label.setText(f"전체 문서 보기 | 총 청크 {len(self.chunks)}개")
            _apply_highlight(self.text, content, self.query)
            return

        chunk = self._current_chunk()
        if chunk is None:
            self.info_label.setText("근거 청크 정보가 없어 대표 본문을 표시합니다.")
            _apply_highlight(self.text, str(self.result_data.get("content", "") or ""), self.query)
            return

        current_idx = int(chunk.get("chunk_idx", 0) or 0) + 1
        total_matches = max(1, len(self.matched_chunk_indices))
        self.info_label.setText(
            f"근거 청크 보기 | 현재 청크 #{current_idx} | 근거 {self._matched_position + 1}/{total_matches}"
        )
        _apply_highlight(self.text, str(chunk.get("content", "") or ""), self.query)


class DebugDetailsDialog(QDialog):
    """TaskResult.debug(스택트레이스/컨텍스트) 표시 + 복사용 경량 다이얼로그."""

    def __init__(self, title: str, details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 600)

        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(details or "")
        layout.addWidget(self.text, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("복사")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy(self):
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.text.toPlainText())
