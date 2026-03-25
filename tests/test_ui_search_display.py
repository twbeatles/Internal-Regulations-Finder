# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit
from typing import cast

from regfinder.ui_components import ResultCard, ResultDetailDialog, SearchHistory


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is not None:
        return cast(QApplication, app)
    return QApplication([])


def test_result_card_uses_ranking_score_and_evidence_label():
    app = _get_app()
    card = ResultCard(
        1,
        {
            "source": "휴가규정.pdf",
            "path": r"C:\docs\휴가규정.pdf",
            "content": "휴가 규정 본문",
            "score": 0.82,
            "vec_score": 0.61,
            "bm25_score": 0.44,
            "match_count": 3,
            "snippet_chunk_idx": 1,
        },
        lambda text: None,
        font_size=12,
        query="휴가를",
    )

    labels = card.findChildren(QLabel)
    ranking_label = next(label for label in labels if label.text() == "랭킹 82")
    evidence_label = next(label for label in labels if "근거 청크 3개" in label.text())

    assert "상대 랭킹 점수: 82" in ranking_label.toolTip()
    assert "벡터: 61" in ranking_label.toolTip()
    assert "키워드: 44" in ranking_label.toolTip()
    assert evidence_label.text() == "근거 청크 3개 | 대표 청크 #2"
    card.close()
    card.deleteLater()
    app.processEvents()


def test_result_card_highlights_compact_query_against_spaced_text():
    app = _get_app()
    card = ResultCard(
        1,
        {
            "source": "휴가규정.pdf",
            "path": r"C:\docs\휴가규정.pdf",
            "content": "휴가 규정 본문",
            "score": 0.82,
            "vec_score": 0.61,
            "bm25_score": 0.44,
            "match_count": 1,
            "snippet_chunk_idx": 0,
        },
        lambda text: None,
        font_size=12,
        query="휴가규정",
    )

    text_edit = next(widget for widget in card.findChildren(QTextEdit))
    doc = text_edit.document()
    highlighted = set()
    for idx in range(len(text_edit.toPlainText())):
        cursor = QTextCursor(doc)
        cursor.setPosition(idx)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            1,
        )
        if cursor.charFormat().background().color().name().lower() == "#e94560":
            highlighted.add(idx)

    assert {0, 1, 2, 3, 4}.issubset(highlighted)
    card.close()
    card.deleteLater()
    app.processEvents()


def test_result_card_updates_font_size_and_file_link_tooltip():
    app = _get_app()
    card = ResultCard(
        1,
        {
            "source": "휴가규정.pdf",
            "path": r"C:\docs\휴가규정.pdf",
            "content": "휴가 규정 본문",
            "score": 0.82,
            "vec_score": 0.61,
            "bm25_score": 0.44,
            "match_count": 2,
            "snippet_chunk_idx": 0,
        },
        lambda text: None,
        font_size=12,
        query="휴가",
        on_details=lambda item: None,
    )

    file_label = next(label for label in card.findChildren(QLabel) if label.text() == "휴가규정.pdf")
    assert "클릭하여 파일 열기" in file_label.toolTip()
    assert any(button.text() == "🧾 상세" for button in card.findChildren(QPushButton))

    card.set_font_size(18)
    text_edit = next(widget for widget in card.findChildren(QTextEdit))
    assert text_edit.font().pointSize() == 18

    card.close()
    card.deleteLater()
    app.processEvents()


def test_result_detail_dialog_supports_evidence_navigation_and_full_view():
    app = _get_app()
    dialog = ResultDetailDialog(
        {
            "source": "휴가규정.pdf",
            "path": r"C:\docs\휴가규정.pdf",
            "content": "대표 본문",
            "score": 0.88,
            "match_count": 2,
            "snippet_chunk_idx": 1,
            "matched_chunk_indices": [1, 3],
        },
        [
            {"chunk_idx": 0, "content": "첫 번째 청크", "source": "휴가규정.pdf", "path": r"C:\docs\휴가규정.pdf", "mtime": 1},
            {"chunk_idx": 1, "content": "두 번째 청크", "source": "휴가규정.pdf", "path": r"C:\docs\휴가규정.pdf", "mtime": 1},
            {"chunk_idx": 2, "content": "세 번째 청크", "source": "휴가규정.pdf", "path": r"C:\docs\휴가규정.pdf", "mtime": 1},
            {"chunk_idx": 3, "content": "네 번째 청크", "source": "휴가규정.pdf", "path": r"C:\docs\휴가규정.pdf", "mtime": 1},
        ],
        query="청크",
        font_size=14,
    )

    assert "현재 청크 #2" in dialog.info_label.text()
    assert "두 번째 청크" in dialog.text.toPlainText()

    dialog._move_match(1)
    assert "현재 청크 #4" in dialog.info_label.text()
    assert "네 번째 청크" in dialog.text.toPlainText()

    dialog._show_full_mode()
    assert "전체 문서 보기" in dialog.info_label.text()
    assert "첫 번째 청크" in dialog.text.toPlainText()
    assert "네 번째 청크" in dialog.text.toPlainText()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_search_history_loads_legacy_and_extended_schema(monkeypatch, tmp_path):
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            [
                {"q": "휴가"},
                "인사",
                {
                    "q": "복리후생",
                    "filters": {"extension": ".pdf", "filename": "규정", "path": "hr"},
                    "sort_by": "mtime_desc",
                    "k": "5",
                    "hybrid": False,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("regfinder.ui_components.get_history_path", lambda: str(history_path))

    history = SearchHistory()

    assert history.get(3)[0]["filters"] == {"extension": "", "filename": "", "path": ""}
    assert history.get(3)[1]["q"] == "인사"
    assert history.get(3)[2] == {
        "q": "복리후생",
        "filters": {"extension": ".pdf", "filename": "규정", "path": "hr"},
        "sort_by": "mtime_desc",
        "k": 5,
        "hybrid": False,
    }

    history.add("신규", filters={"extension": ".txt", "filename": "안내", "path": "ops"}, sort_by="filename_asc", k=4, hybrid=True)
    saved = json.loads(history_path.read_text(encoding="utf-8"))
    assert saved[0] == {
        "q": "신규",
        "filters": {"extension": ".txt", "filename": "안내", "path": "ops"},
        "sort_by": "filename_asc",
        "k": 4,
        "hybrid": True,
    }
