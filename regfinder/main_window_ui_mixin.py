# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from .app_types import AppConfig


class MainWindowUIBuilderMixin:
    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"{AppConfig.APP_NAME} v{AppConfig.APP_VERSION}")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        self._setup_main_layout()
        self._setup_header()
        self._setup_tabs()
        self._setup_shortcuts()

    def _setup_main_layout(self):
        """메인 레이아웃 설정"""
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

    def _setup_header(self):
        """헤더 영역 생성"""
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background: #0f3460;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel(f"📚 {AppConfig.APP_NAME}")
        logo.setFont(QFont("", 16, QFont.Weight.Bold))
        logo.setStyleSheet("color: white;")
        header_layout.addWidget(logo)
        header_layout.addStretch()

        self.status_label = QLabel("🔄 초기화 중...")
        self.status_label.setStyleSheet("color: #f59e0b;")
        header_layout.addWidget(self.status_label)

        version = QLabel(f"v{AppConfig.APP_VERSION}")
        version.setStyleSheet("color: #666;")
        header_layout.addWidget(version)

        self.main_layout.addWidget(header)

    def _setup_tabs(self):
        """탭 위젯 설정"""
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.main_layout.addWidget(self.tabs)

        self.tabs.addTab(self._create_search_view(), "🔍 검색")
        self.tabs.addTab(self._create_files_view(), "📄 파일")
        self.tabs.addTab(self._create_bookmarks_view(), "⭐ 북마크")
        self.tabs.addTab(self._create_diagnostics_view(), "🧰 진단")
        self.tabs.addTab(self._create_settings_view(), "⚙️ 설정")

    def _setup_shortcuts(self):
        """키보드 단축키 설정"""
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._open_folder)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._focus_search)

    def _focus_search(self):
        """검색창에 포커스"""
        self.tabs.setCurrentIndex(0)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _create_search_view(self) -> QWidget:
        """검색 탭 뷰 생성"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(self._create_folder_control_panel())

        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.result_layout.setContentsMargins(10, 10, 10, 10)
        self.result_layout.setSpacing(12)
        self.result_area.setWidget(self.result_container)

        self._show_empty_state("welcome")
        layout.addWidget(self.result_area, 1)
        layout.addWidget(self._create_search_input_panel())
        return view

    def _create_folder_control_panel(self) -> QFrame:
        """폴더 열기 및 새로고침 패널 생성"""
        panel = QFrame()
        panel.setObjectName("card")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(15, 12, 15, 12)

        self.folder_btn = QPushButton("📂 폴더 열기")
        self.folder_btn.setEnabled(False)
        self.folder_btn.clicked.connect(self._open_folder)
        layout.addWidget(self.folder_btn)

        self.recent_btn = QPushButton("🕐 최근")
        self.recent_btn.setEnabled(False)
        self.recent_btn.clicked.connect(self._load_recent)
        layout.addWidget(self.recent_btn)

        self.folder_label = QLabel("폴더를 선택하세요")
        self.folder_label.setStyleSheet("color: #888;")
        layout.addWidget(self.folder_label, 1)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(self.refresh_btn)

        return panel

    def _create_search_input_panel(self) -> QFrame:
        """검색 입력 및 설정 패널 생성"""
        panel = QFrame()
        panel.setObjectName("card")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(15, 12, 15, 12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요... (최소 2글자)")
        self.search_input.setEnabled(False)
        self.search_input.returnPressed.connect(self._search)
        layout.addWidget(self.search_input, 1)

        self.filename_filter_input = QLineEdit()
        self.filename_filter_input.setPlaceholderText("파일명 필터")
        self.filename_filter_input.setToolTip("파일명 포함 필터")
        self.filename_filter_input.setFixedWidth(140)
        self.filename_filter_input.setText(self.search_filters.get("filename", ""))
        layout.addWidget(self.filename_filter_input)

        self.path_filter_input = QLineEdit()
        self.path_filter_input.setPlaceholderText("경로 필터")
        self.path_filter_input.setToolTip("전체 경로 포함 필터")
        self.path_filter_input.setFixedWidth(160)
        self.path_filter_input.setText(self.search_filters.get("path", ""))
        layout.addWidget(self.path_filter_input)

        self.ext_filter_combo = QComboBox()
        self.ext_filter_combo.setFixedWidth(95)
        self.ext_filter_combo.addItem("형식:전체", "")
        for ext in AppConfig.SUPPORTED_EXTENSIONS:
            self.ext_filter_combo.addItem(ext, ext)
        idx = self.ext_filter_combo.findData(self.search_filters.get("extension", ""))
        self.ext_filter_combo.setCurrentIndex(idx if idx >= 0 else 0)
        layout.addWidget(self.ext_filter_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.setFixedWidth(120)
        self.sort_combo.addItem("점수순", "score_desc")
        self.sort_combo.addItem("파일명순", "filename_asc")
        self.sort_combo.addItem("최근 수정순", "mtime_desc")
        sort_idx = self.sort_combo.findData(self.sort_by)
        self.sort_combo.setCurrentIndex(sort_idx if sort_idx >= 0 else 0)
        layout.addWidget(self.sort_combo)

        self.history_btn = QPushButton("🕑")
        self.history_btn.setFixedWidth(40)
        self.history_btn.setToolTip("최근 검색어")
        self.history_btn.clicked.connect(self._show_history_menu)
        layout.addWidget(self.history_btn)

        self.k_spin = QSpinBox()
        self.k_spin.setRange(1, 10)
        self.k_spin.setValue(AppConfig.DEFAULT_SEARCH_RESULTS)
        self.k_spin.setPrefix("결과: ")
        self.k_spin.setFixedWidth(100)
        layout.addWidget(self.k_spin)

        self.search_btn = QPushButton("🔍 검색")
        self.search_btn.setEnabled(False)
        self.search_btn.clicked.connect(self._search)
        layout.addWidget(self.search_btn)

        return panel

    def _create_files_view(self) -> QWidget:
        """파일 탭 뷰 생성"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)

        stats_frame = QFrame()
        stats_frame.setObjectName("statCard")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(20, 15, 20, 15)

        self.stats_files = QLabel("📄 0개 파일")
        self.stats_files.setFont(QFont("", 12, QFont.Weight.Bold))
        stats_layout.addWidget(self.stats_files)

        self.stats_chunks = QLabel("📊 0 청크")
        stats_layout.addWidget(self.stats_chunks)

        self.stats_size = QLabel("💾 0 B")
        stats_layout.addWidget(self.stats_size)
        stats_layout.addStretch()

        self.open_folder_btn = QPushButton("📂 폴더 열기")
        self.open_folder_btn.setFixedWidth(120)
        self.open_folder_btn.clicked.connect(self._open_current_folder)
        stats_layout.addWidget(self.open_folder_btn)
        layout.addWidget(stats_frame)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["상태", "파일명", "크기", "청크"])
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSortingEnabled(True)
        self.file_table.setToolTip("더블클릭으로 파일 열기")
        self.file_table.doubleClicked.connect(self._open_selected_file)
        layout.addWidget(self.file_table)
        return view

    def _create_settings_view(self) -> QWidget:
        """설정 탭 뷰 생성"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        search_card = self._create_setting_card("🔍 검색 설정")
        self.hybrid_check = QCheckBox("하이브리드 검색 (벡터 + 키워드)")
        self.hybrid_check.setChecked(self.hybrid)
        self.hybrid_check.stateChanged.connect(lambda: setattr(self, "hybrid", self.hybrid_check.isChecked()))
        self.hybrid_check.setToolTip("벡터 검색과 키워드 검색을 결합하여 더 정확한 결과 제공")
        search_card.layout().addWidget(self.hybrid_check)

        self.recursive_check = QCheckBox("하위 폴더 포함 검색")
        self.recursive_check.setChecked(self.recursive)
        self.recursive_check.setToolTip("선택한 폴더의 모든 하위 폴더에서도 문서를 검색합니다")
        self.recursive_check.stateChanged.connect(lambda: setattr(self, "recursive", self.recursive_check.isChecked()))
        search_card.layout().addWidget(self.recursive_check)
        layout.addWidget(search_card)

        display_card = self._create_setting_card("🎨 표시 설정")
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("결과 폰트 크기:"))
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(AppConfig.MIN_FONT_SIZE, AppConfig.MAX_FONT_SIZE)
        self.font_slider.setValue(self.font_size)
        self.font_slider.valueChanged.connect(self._on_font_size_changed)
        font_row.addWidget(self.font_slider, 1)
        self.font_size_label = QLabel(f"{self.font_size}pt")
        self.font_size_label.setStyleSheet("color: #e94560; font-weight: bold;")
        font_row.addWidget(self.font_size_label)
        display_card.layout().addLayout(font_row)
        layout.addWidget(display_card)

        model_card = self._create_setting_card("🤖 AI 모델")
        self.model_combo = QComboBox()
        self.model_combo.addItems(AppConfig.AVAILABLE_MODELS.keys())
        self.model_combo.setCurrentText(self.model_name)
        self.model_combo.currentTextChanged.connect(lambda t: setattr(self, "model_name", t))
        model_card.layout().addWidget(self.model_combo)

        model_btn_row = QHBoxLayout()
        reload_model_btn = QPushButton("🔄 모델 즉시 변경")
        reload_model_btn.clicked.connect(self._reload_model)
        model_btn_row.addWidget(reload_model_btn)

        download_all_btn = QPushButton("📥 오프라인 모델 다운로드")
        download_all_btn.setToolTip("모든 모델을 사전 다운로드하여 오프라인에서 사용")
        download_all_btn.clicked.connect(self._download_all_models)
        model_btn_row.addWidget(download_all_btn)
        model_btn_row.addStretch()
        model_card.layout().addLayout(model_btn_row)

        self.model_status_label = QLabel("")
        self.model_status_label.setStyleSheet("color: #888; font-size: 12px;")
        self._update_model_status()
        model_card.layout().addWidget(self.model_status_label)

        model_card.layout().addWidget(QLabel("⚠️ 모델 변경 시 기존 인덱스가 초기화됩니다"))
        layout.addWidget(model_card)

        data_card = self._create_setting_card("🗂️ 데이터 관리")
        btn_row = QHBoxLayout()
        clear_cache_btn = QPushButton("🗑️ 캐시 삭제")
        clear_cache_btn.setStyleSheet("background: #dc2626;")
        clear_cache_btn.clicked.connect(self._clear_cache)
        btn_row.addWidget(clear_cache_btn)
        clear_history_btn = QPushButton("🕐 히스토리 삭제")
        clear_history_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(clear_history_btn)
        diag_btn = QPushButton("🧰 진단 내보내기")
        diag_btn.setToolTip("환경/설정/로그/캐시 요약을 zip으로 내보냅니다.\n(문서 원문/청크 내용/벡터 인덱스는 포함하지 않음)")
        diag_btn.clicked.connect(self._export_diagnostics)
        btn_row.addWidget(diag_btn)
        btn_row.addStretch()
        data_card.layout().addLayout(btn_row)

        self.cache_size_label = QLabel("")
        self.cache_size_label.setStyleSheet("color: #888; font-size: 12px;")
        self._update_cache_size_display()
        data_card.layout().addWidget(self.cache_size_label)

        self.internal_state_label = QLabel("")
        self.internal_state_label.setStyleSheet("color: #888; font-size: 11px;")
        self.internal_state_label.setWordWrap(True)
        data_card.layout().addWidget(self.internal_state_label)
        layout.addWidget(data_card)

        layout.addStretch()
        return view

    def _create_setting_card(self, title: str) -> QFrame:
        """설정 카드 프레임 생성"""
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)

        title_label = QLabel(title)
        title_label.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(title_label)
        return card
