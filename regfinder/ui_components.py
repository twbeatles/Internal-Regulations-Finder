# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .app_types import AppConfig
from .file_utils import FileUtils
from .runtime import get_history_path, logger

class SearchHistory:
    def __init__(self):
        self.items: List[str] = []
        self.path = get_history_path()
        self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.items = [h['q'] for h in data[:AppConfig.MAX_HISTORY_SIZE]]
            except Exception:
                logger.warning(f"히스토리 로드 실패: {self.path}")
                self.items = []
    
    def _save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump([{'q': q} for q in self.items], f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"히스토리 저장 실패: {e}")
    
    def add(self, query: str):
        self.items = [q for q in self.items if q != query]
        self.items.insert(0, query)
        self.items = self.items[:AppConfig.MAX_HISTORY_SIZE]
        self._save()
    
    def get(self, count: int = 10): return self.items[:count]
    def clear(self): self.items = []; self._save()


# ============================================================================
# 결과 카드
# ============================================================================
class ResultCard(QFrame):
    """검색 결과를 표시하는 카드 위젯"""
    
    def __init__(self, idx: int, data: Dict, on_copy, font_size: int = 12, query: str = ""):
        super().__init__()
        self.setObjectName("resultCard")
        self.data = data
        self.query = query
        
        # 그림자 효과
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        
        # 헤더
        header = QHBoxLayout()
        header.setSpacing(12)
        
        # 결과 번호 배지
        badge = QLabel(f"{idx}")
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("""
            background: #e94560; 
            color: white; 
            border-radius: 14px; 
            font-weight: bold;
            font-size: 12px;
        """)
        header.addWidget(badge)
        
        # 파일명
        source = QLabel(data['source'])
        source.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        if data.get('path'):
            source.setToolTip(f"📁 {data['path']}\n더블클릭으로 파일 열기")
            source.setCursor(Qt.CursorShape.PointingHandCursor)
            source.mousePressEvent = lambda e: FileUtils.open_file(data['path']) if e.button() == Qt.MouseButton.LeftButton else None
        header.addWidget(source)
        
        header.addStretch()
        
        # 점수 표시
        score = int(data.get('score', 0) * 100)
        score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
        
        score_container = QHBoxLayout()
        score_container.setSpacing(8)
        
        pbar = QProgressBar()
        pbar.setFixedWidth(80)
        pbar.setFixedHeight(8)
        pbar.setValue(score)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"""
            QProgressBar {{ background: #0f3460; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {score_color}; border-radius: 4px; }}
        """)
        score_container.addWidget(pbar)
        
        score_lbl = QLabel(f"{score}%")
        score_lbl.setStyleSheet(f"color: {score_color}; font-weight: bold; font-size: 13px;")
        score_lbl.setToolTip(f"유사도: {score}%\n벡터: {int(data.get('vec_score', 0)*100)}% | 키워드: {int(data.get('bm25_score', 0)*100)}%")
        score_container.addWidget(score_lbl)
        
        header.addLayout(score_container)
        
        # 버튼들
        btn_container = QHBoxLayout()
        btn_container.setSpacing(6)
        
        copy_btn = QPushButton("📋 복사")
        copy_btn.setFixedHeight(30)
        copy_btn.setFixedWidth(75)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: on_copy(data['content']))
        btn_container.addWidget(copy_btn)
        
        if data.get('path'):
            open_btn = QPushButton("📂 열기")
            open_btn.setFixedHeight(30)
            open_btn.setFixedWidth(75)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda: FileUtils.open_file(data['path']))
            btn_container.addWidget(open_btn)
        
        header.addLayout(btn_container)
        layout.addLayout(header)
        
        # 내용 (검색어 하이라이트 포함)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setFont(QFont("", font_size))
        content.setMinimumHeight(80)
        content.setMaximumHeight(180)
        
        # 검색어 하이라이트 적용
        self._apply_highlight(content, data['content'], query)
        
        layout.addWidget(content)
    
    def _apply_highlight(self, text_edit: QTextEdit, content: str, query: str):
        """검색어를 하이라이트 처리"""
        from PyQt6.QtGui import QTextCursor, QTextCharFormat
        
        text_edit.setPlainText(content)
        
        if not query or len(query) < 2:
            return
        
        # 검색어를 여러 단어로 분리하여 각각 하이라이트
        keywords = [k.strip() for k in query.split() if len(k.strip()) >= 2]
        
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#e94560"))
        highlight_format.setForeground(QColor("white"))
        
        cursor = text_edit.textCursor()
        
        for keyword in keywords:
            # 대소문자 무시 검색
            text = content.lower()
            keyword_lower = keyword.lower()
            start = 0
            
            while True:
                pos = text.find(keyword_lower, start)
                if pos == -1:
                    break
                
                cursor.setPosition(pos)
                cursor.setPosition(pos + len(keyword), QTextCursor.MoveMode.KeepAnchor)
                cursor.mergeCharFormat(highlight_format)
                start = pos + len(keyword)
        
        # 커서를 처음으로 이동
        cursor.setPosition(0)
        text_edit.setTextCursor(cursor)


# ============================================================================
# 빈 상태 위젯
# ============================================================================
class EmptyStateWidget(QFrame):
    """빈 상태를 표시하는 위젯"""
    
    def __init__(self, icon: str = "📂", title: str = "", description: str = ""):
        super().__init__()
        self.setObjectName("card")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 아이콘
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # 제목
        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("", 16, QFont.Weight.Bold))
            title_label.setStyleSheet("color: #eaeaea;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_label)
        
        # 설명
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #888; font-size: 13px;")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)


# ============================================================================
# 프로그레스 다이얼로그
# ============================================================================
class ProgressDialog(QFrame):
    """문서 처리 진행 상황을 표시하는 다이얼로그"""
    
    canceled = pyqtSignal()
    
    def __init__(self, parent=None, title: str = "처리 중"):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedSize(400, 180)
        
        # 그림자 효과
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 제목
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("", 14, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 현재 처리 중인 항목
        self.status_label = QLabel("준비 중...")
        self.status_label.setStyleSheet("color: #888;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(12)
        layout.addWidget(self.progress_bar)
        
        # 상세 정보
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: #666; font-size: 11px;")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_label)
        
        # 취소 버튼
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet("background: #dc2626;")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)
    
    def _on_cancel(self):
        """취소 버튼 클릭 처리"""
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("취소 중...")
        self.canceled.emit()
    
    def update_progress(self, percent: int, status: str):
        """진행 상황 업데이트"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)
        self.detail_label.setText(f"{percent}% 완료")


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
        QApplication.clipboard().setText(self.text.toPlainText())
