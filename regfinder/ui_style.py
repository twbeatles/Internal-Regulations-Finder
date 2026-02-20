# -*- coding: utf-8 -*-
from __future__ import annotations

DARK_STYLE = """
/* 기본 위젯 */
QMainWindow, QWidget { background-color: #1a1a2e; color: #eaeaea; }
QLabel { color: #eaeaea; }

/* 탭 위젯 */
QTabWidget::pane { border: none; background: #16213e; border-radius: 8px; }
QTabBar::tab { background: #0f3460; color: #aaa; padding: 12px 24px; margin-right: 2px; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: bold; }
QTabBar::tab:selected { background: #16213e; color: white; }
QTabBar::tab:hover:!selected { background: #1a4a70; color: #ddd; }

/* 입력 필드 */
QLineEdit { background: #0f3460; border: 2px solid #1a1a2e; border-radius: 8px; padding: 10px 15px; color: white; font-size: 14px; selection-background-color: #e94560; }
QLineEdit:focus { border-color: #e94560; }
QLineEdit:disabled { background: #2a2a3e; color: #666; }

/* 버튼 */
QPushButton { background: #0f3460; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
QPushButton:hover { background: #e94560; }
QPushButton:pressed { background: #c73a52; }
QPushButton:disabled { background: #2a2a3e; color: #666; }

/* 텍스트 에디터 */
QTextEdit { background: #0f3460; border: none; border-radius: 6px; padding: 10px; color: #eaeaea; selection-background-color: #e94560; }

/* 프로그레스 바 */
QProgressBar { background: #0f3460; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e94560, stop:1 #0f3460); border-radius: 4px; }

/* 스크롤 영역 */
QScrollArea { border: none; background: transparent; }

/* 콤보박스 */
QComboBox { background: #0f3460; border: 2px solid #1a1a2e; border-radius: 6px; padding: 8px 12px; color: white; min-width: 100px; }
QComboBox:hover { border-color: #e94560; }
QComboBox:focus { border-color: #e94560; }
QComboBox::drop-down { border: none; width: 30px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #e94560; margin-right: 10px; }
QComboBox QAbstractItemView { background: #0f3460; border: 2px solid #e94560; border-radius: 4px; selection-background-color: #e94560; color: white; padding: 4px; }

/* 스핀박스 */
QSpinBox { background: #0f3460; border: 2px solid #1a1a2e; border-radius: 6px; padding: 6px 10px; color: white; min-width: 80px; }
QSpinBox:hover { border-color: #e94560; }
QSpinBox:focus { border-color: #e94560; }
QSpinBox::up-button, QSpinBox::down-button { background: #1a4a70; border: none; width: 20px; border-radius: 3px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #e94560; }
QSpinBox::up-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid white; }
QSpinBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid white; }

/* 체크박스 */
QCheckBox { color: #eaeaea; spacing: 8px; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 4px; background: #0f3460; border: 2px solid #1a1a2e; }
QCheckBox::indicator:hover { border-color: #e94560; }
QCheckBox::indicator:checked { background: #e94560; border-color: #e94560; }

/* 테이블 */
QTableWidget { background: #16213e; border: none; gridline-color: #0f3460; alternate-background-color: #1a2845; }
QTableWidget::item { padding: 8px; border: none; }
QTableWidget::item:selected { background: #e94560; color: white; }
QTableWidget::item:hover:!selected { background: #1a4a70; }
QHeaderView::section { background: #0f3460; color: white; padding: 10px; border: none; font-weight: bold; }
QHeaderView::section:hover { background: #e94560; }

/* 스크롤바 - 세로 */
QScrollBar:vertical { background: #1a1a2e; width: 12px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical { background: #0f3460; border-radius: 5px; min-height: 30px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #e94560; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

/* 스크롤바 - 가로 */
QScrollBar:horizontal { background: #1a1a2e; height: 12px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal { background: #0f3460; border-radius: 5px; min-width: 30px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #e94560; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* 툴팁 */
QToolTip { background: #16213e; color: white; border: 1px solid #e94560; padding: 8px 12px; border-radius: 6px; font-size: 12px; }

/* 메시지박스/다이얼로그 */
QMessageBox { background: #1a1a2e; }
QMessageBox QLabel { color: #eaeaea; }
QMessageBox QPushButton { min-width: 80px; }

/* 카드 프레임 */
QFrame#card { background: #16213e; border-radius: 12px; border: 1px solid #0f3460; }
QFrame#card:hover { border-color: #1a4a70; }
QFrame#statCard { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f3460, stop:1 #16213e); border-radius: 12px; border: 1px solid #1a4a70; }
QFrame#resultCard { background: #16213e; border-radius: 12px; border: 1px solid #0f3460; }
QFrame#resultCard:hover { border-color: #e94560; }

/* 슬라이더 */
QSlider::groove:horizontal { background: #0f3460; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #e94560; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: #ff6b8a; }
QSlider::sub-page:horizontal { background: #e94560; border-radius: 3px; }
"""
