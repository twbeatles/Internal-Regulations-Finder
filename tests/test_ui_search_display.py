# -*- coding: utf-8 -*-
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QLabel, QTextEdit
from typing import cast

from regfinder.ui_components import ResultCard


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
