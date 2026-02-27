# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from .app_types import AppConfig, FileStatus, TaskResult
from .file_utils import FileUtils
from .qa_system import RegulationQASystem
from .runtime import get_config_path, get_data_directory, get_models_directory, logger
from .ui_components import (
    DebugDetailsDialog,
    EmptyStateWidget,
    ProgressDialog,
    ResultCard,
    SearchHistory,
)
from .workers import DocumentProcessorThread, ModelDownloadThread, ModelLoaderThread, SearchThread

class MainWindow(QMainWindow):

    def __init__(self, qa: RegulationQASystem):
        super().__init__()
        self.qa = qa
        self.history = SearchHistory()
        self.last_folder = ""
        self.model_name = AppConfig.DEFAULT_MODEL
        self.font_size = AppConfig.DEFAULT_FONT_SIZE
        self.hybrid = True
        self.worker = None
        self.download_worker = None
        self.progress_dialog = None
        self._pdf_password_session = {}
        self.status_timer = None  # 상태 레이블 타이머 관리
        
        self._load_config()
        self._init_ui()
        self._update_internal_state_display()
        QTimer.singleShot(100, self._load_model)
    
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
        self.tabs.addTab(self._create_settings_view(), "⚙️ 설정")
    
    def _setup_shortcuts(self):
        """키보드 단축키 설정"""
        # Ctrl+O: 폴더 열기
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._open_folder)
        # Ctrl+F: 검색창 포커스
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._focus_search)
    
    def _focus_search(self):
        """검색창에 포커스"""
        self.tabs.setCurrentIndex(0)  # 검색 탭으로 이동
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def _create_search_view(self) -> QWidget:
        """검색 탭 뷰 생성"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. 상단: 폴더 로드 및 제어 레이어
        layout.addWidget(self._create_folder_control_panel())
        
        # 2. 중앙: 결과 표시 레이어
        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.result_layout.setContentsMargins(10, 10, 10, 10)
        self.result_layout.setSpacing(12)
        self.result_area.setWidget(self.result_container)
        
        # 초기 빈 상태 표시
        self._show_empty_state("welcome")
        layout.addWidget(self.result_area, 1)
        
        # 3. 하단: 검색 필터 및 입력 레이어
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
        
        # 1. 상단: 파일 통계
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
        
        # 2. 중앙: 파일 리스트 테이블
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
        
        # 1. 검색 설정
        search_card = self._create_setting_card("🔍 검색 설정")
        self.hybrid_check = QCheckBox("하이브리드 검색 (벡터 + 키워드)")
        self.hybrid_check.setChecked(self.hybrid)
        self.hybrid_check.stateChanged.connect(lambda: setattr(self, 'hybrid', self.hybrid_check.isChecked()))
        self.hybrid_check.setToolTip("벡터 검색과 키워드 검색을 결합하여 더 정확한 결과 제공")
        search_card.layout().addWidget(self.hybrid_check)
        
        # 하위 폴더 포함 옵션
        self.recursive_check = QCheckBox("하위 폴더 포함 검색")
        self.recursive_check.setChecked(False)
        self.recursive_check.setToolTip("선택한 폴더의 모든 하위 폴더에서도 문서를 검색합니다")
        search_card.layout().addWidget(self.recursive_check)
        layout.addWidget(search_card)
        
        # 2. 표시 설정
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
        
        # 3. 모델 설정
        model_card = self._create_setting_card("🤖 AI 모델")
        self.model_combo = QComboBox()
        self.model_combo.addItems(AppConfig.AVAILABLE_MODELS.keys())
        self.model_combo.setCurrentText(self.model_name)
        self.model_combo.currentTextChanged.connect(lambda t: setattr(self, 'model_name', t))
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
        
        # 모델 상태 레이블
        self.model_status_label = QLabel("")
        self.model_status_label.setStyleSheet("color: #888; font-size: 12px;")
        self._update_model_status()
        model_card.layout().addWidget(self.model_status_label)
        
        model_card.layout().addWidget(QLabel("⚠️ 모델 변경 시 기존 인덱스가 초기화됩니다"))
        layout.addWidget(model_card)
        
        # 4. 데이터 관리
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
        
        # 캐시 사용량 표시
        self.cache_size_label = QLabel("")
        self.cache_size_label.setStyleSheet("color: #888; font-size: 12px;")
        self._update_cache_size_display()
        data_card.layout().addWidget(self.cache_size_label)

        # 내부 상태(디버깅용) 표시
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
    
    def _on_font_size_changed(self, value: int):
        """폰트 크기 변경 처리"""
        self.font_size = value
        self.font_size_label.setText(f"{value}pt")
        self._save_config()
    
    def _load_config(self):
        """사용자 환경 설정 로드 (손상 시 기본값 복원)"""
        path = get_config_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.last_folder = cfg.get("folder", "")
                self.model_name = cfg.get("model", AppConfig.DEFAULT_MODEL)
                self.font_size = cfg.get("font", AppConfig.DEFAULT_FONT_SIZE)
                self.hybrid = cfg.get("hybrid", True)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"설정 파일 손상, 기본값으로 복원: {e}")
                # 손상된 설정 파일 삭제 후 기본값 사용
                try:
                    os.remove(path)
                except OSError as e:
                    logger.debug(f"손상된 설정 파일 삭제 실패(무시): {e}")
                self._reset_to_defaults()
            except Exception as e:
                logger.warning(f"환경 설정 로드 오류: {e}")
                self._reset_to_defaults()
    
    def _reset_to_defaults(self):
        """설정을 기본값으로 초기화"""
        self.last_folder = ""
        self.model_name = AppConfig.DEFAULT_MODEL
        self.font_size = AppConfig.DEFAULT_FONT_SIZE
        self.hybrid = True
    
    def _save_config(self):
        try:
            with open(get_config_path(), 'w', encoding='utf-8') as f:
                json.dump({"folder": self.last_folder, "model": self.model_name, "font": self.font_size, "hybrid": self.hybrid}, f)
        except Exception as e:
            logger.warning(f"설정 저장 실패: {e}")

    def _set_search_controls_enabled(self, enabled: bool):
        self.search_input.setEnabled(enabled)
        self.search_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def _close_progress_dialog(self):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is None:
            return
        try:
            dlg.close()
            dlg.deleteLater()
        except Exception as e:
            logger.debug(f"진행 다이얼로그 종료 실패(무시): {e}")
        self.progress_dialog = None

    def _stop_worker_thread(self, worker, name: str, timeout_ms: int = 3000):
        if worker is None:
            return
        try:
            if worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                if not worker.wait(timeout_ms):
                    logger.warning(f"{name} 스레드 종료 타임아웃({timeout_ms}ms)")
            else:
                worker.wait(100)
        except Exception as e:
            logger.warning(f"{name} 스레드 종료 중 오류: {e}")

    def _collect_pdf_passwords(self, files):
        process_files = []
        pdf_passwords = {}
        skipped = []
        for fp in files:
            if os.path.splitext(fp)[1].lower() != ".pdf":
                process_files.append(fp)
                continue

            encrypted, error = self.qa.extractor.check_pdf_encrypted(fp)
            if error:
                process_files.append(fp)
                continue
            if not encrypted:
                process_files.append(fp)
                continue

            if fp in self._pdf_password_session:
                pdf_passwords[fp] = self._pdf_password_session[fp]
                process_files.append(fp)
                continue

            prompt = (
                f"파일: {os.path.basename(fp)}\n"
                "암호화된 PDF입니다. 비밀번호를 입력하세요.\n"
                "취소하면 이 파일은 건너뜁니다."
            )
            password, ok = QInputDialog.getText(
                self,
                "암호화 PDF 비밀번호",
                prompt,
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                skipped.append(f"{os.path.basename(fp)} (암호 입력 취소)")
                continue
            password = password.strip()
            if not password:
                skipped.append(f"{os.path.basename(fp)} (비밀번호 미입력)")
                continue

            self._pdf_password_session[fp] = password
            pdf_passwords[fp] = password
            process_files.append(fp)
        return process_files, pdf_passwords, skipped
    
    def _load_model(self):
        self.status_label.setText("🔄 모델 로딩 중...")
        worker = ModelLoaderThread(self.qa, self.model_name)
        worker.progress.connect(lambda m: self.status_label.setText(f"🔄 {m}"))
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.worker = worker
        worker.start()
    
    def _on_model_loaded(self, result):
        self.worker = None
        if result.success:
            self.status_label.setText(f"✅ {result.message}")
            self.status_label.setStyleSheet("color: #10b981;")
            self.folder_btn.setEnabled(True)
            if self.last_folder and os.path.isdir(self.last_folder):
                self.recent_btn.setEnabled(True)
            self._update_internal_state_display()
        else:
            self.status_label.setText(f"❌ {result.message}")
            self.status_label.setStyleSheet("color: #ef4444;")
            self.folder_btn.setEnabled(False)
            self.recent_btn.setEnabled(False)
            self._set_search_controls_enabled(False)
            self._update_internal_state_display()
            self._show_task_error("모델 로드 오류", result)
    
    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "규정 폴더 선택")
        if folder:
            self._load_folder(folder)
    
    def _load_recent(self):
        if self.last_folder and os.path.isdir(self.last_folder):
            self._load_folder(self.last_folder)
    
    def _refresh(self):
        if self.last_folder:
            cache = self.qa._get_cache_dir(self.last_folder)
            shutil.rmtree(cache, ignore_errors=True)
            self._load_folder(self.last_folder)
    
    def _reload_model(self):
        """모델 즉시 변경"""
        if QMessageBox.question(
            self, "확인",
            "모델을 변경하면 현재 로드된 문서 인덱스가 초기화됩니다.\n계속하시겠습니까?"
        ) == QMessageBox.StandardButton.Yes:
            # 기존 런타임 상태 초기화
            self.qa.reset_runtime_state(reset_model=True)
            
            # UI 초기화
            self._set_search_controls_enabled(False)
            self.recent_btn.setEnabled(False)
            self._show_empty_state("welcome")
            self._update_file_table()
            self._update_internal_state_display()
            
            # 모델 재로드
            self._save_config()
            self._load_model()
    
    def _open_current_folder(self):
        """현재 선택된 폴더 열기"""
        if self.last_folder and os.path.isdir(self.last_folder):
            FileUtils.open_file(self.last_folder)
        else:
            QMessageBox.information(self, "알림", "선택된 폴더가 없습니다.")

    def _load_folder(self, folder):
        """폴더 로드 및 문서 처리 시작"""
        try:
            # 하위 폴더 포함 여부 확인
            if hasattr(self, 'recursive_check') and self.recursive_check.isChecked():
                files = []
                for root, _, filenames in os.walk(folder):
                    for f in filenames:
                        if os.path.splitext(f)[1].lower() in AppConfig.SUPPORTED_EXTENSIONS:
                            files.append(os.path.join(root, f))
            else:
                files = [os.path.join(folder, f) for f in os.listdir(folder) 
                         if os.path.splitext(f)[1].lower() in AppConfig.SUPPORTED_EXTENSIONS]
        except PermissionError:
            QMessageBox.critical(self, "오류", "폴더 접근 권한이 없습니다.")
            return
        except Exception as e:
            QMessageBox.critical(self, "오류", f"폴더 읽기 실패: {e}")
            return
        
        if not files:
            QMessageBox.warning(self, "경고", f"지원되는 파일이 없습니다.\n\n지원 형식: {', '.join(AppConfig.SUPPORTED_EXTENSIONS)}")
            return

        files, pdf_passwords, skipped_pdf = self._collect_pdf_passwords(files)
        if not files:
            if skipped_pdf:
                skipped_msg = "\n".join(skipped_pdf[:5])
                more_msg = f"\n...외 {len(skipped_pdf) - 5}개" if len(skipped_pdf) > 5 else ""
                QMessageBox.warning(
                    self,
                    "경고",
                    f"처리할 파일이 없습니다.\n\n건너뛴 파일:\n{skipped_msg}{more_msg}",
                )
            else:
                QMessageBox.warning(self, "경고", "처리할 파일이 없습니다.")
            return
        
        self.folder_label.setText(folder)
        self.folder_label.setToolTip(folder)
        self.folder_btn.setEnabled(False)
        
        self.progress_dialog = ProgressDialog(self, "문서 처리 중")
        # 부모 윈도우 중앙에 정확히 배치
        dialog_x = self.x() + (self.width() - self.progress_dialog.width()) // 2
        dialog_y = self.y() + (self.height() - self.progress_dialog.height()) // 2
        self.progress_dialog.move(dialog_x, dialog_y)
        self.progress_dialog.show()
        
        worker = DocumentProcessorThread(
            self.qa,
            folder,
            files,
            pdf_passwords=pdf_passwords,
            ocr_options={"enabled": True},
        )
        worker.progress.connect(self.progress_dialog.update_progress)
        worker.finished.connect(lambda r, skipped=skipped_pdf: self._on_folder_done(r, folder, skipped))
        worker.finished.connect(lambda *_: worker.deleteLater())
        # 취소 시그널 연결
        self.progress_dialog.canceled.connect(worker.cancel)
        self.worker = worker
        worker.start()
    
    def _on_folder_done(self, result, folder, skipped_items=None):
        """폴더 처리 완료 핸들러"""
        skipped_items = list(skipped_items or [])
        self._close_progress_dialog()
        self.folder_btn.setEnabled(True)
        self.worker = None  # 스레드 참조 해제

        merged_failed = skipped_items + list(result.failed_items or [])
        result.failed_items = merged_failed
        
        if result.success:
            self.last_folder = folder
            self._save_config()
            self._set_search_controls_enabled(True)
            self.recent_btn.setEnabled(True)
            self._update_file_table()
            self._update_cache_size_display()
            self._update_internal_state_display()
            self._show_empty_state("ready")
            
            # 상태 표시
            self._show_status(f"✅ {result.message} (청크: {result.data.get('chunks', 0)})", "#10b981")
            self.search_input.setFocus()
            
            # 처리 실패 파일이 있으면 알림
            if merged_failed:
                failed_count = len(merged_failed)
                failed_list = "\n".join(merged_failed[:5])  # 최대 5개만 표시
                more_msg = f"\n...외 {failed_count - 5}개" if failed_count > 5 else ""
                QMessageBox.warning(
                    self, 
                    "일부 파일 처리 실패",
                    f"{failed_count}개 파일 처리 실패:\n\n{failed_list}{more_msg}"
                )
        else:
            self._show_status(f"❌ {result.message}", "#ef4444")
            self._update_internal_state_display()
            self._show_task_error("문서 처리 오류", result)
    
    def _update_file_table(self):
        infos = self.qa.get_file_infos()
        
        # 정렬 비활성화 후 데이터 삽입 (성능 최적화)
        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(len(infos))
        
        icons = {FileStatus.SUCCESS: "✅", FileStatus.CACHED: "💾", FileStatus.FAILED: "❌", FileStatus.PROCESSING: "⏳", FileStatus.PENDING: "⏸️"}
        total_size = 0
        total_chunks = 0
        
        for i, info in enumerate(infos):
            # 상태 아이콘
            status_item = QTableWidgetItem(icons.get(info.status, "?"))
            status_item.setData(Qt.ItemDataRole.UserRole, info.path)  # 파일 경로 저장
            self.file_table.setItem(i, 0, status_item)
            
            # 파일명 (경로 저장)
            name_item = QTableWidgetItem(info.name)
            name_item.setData(Qt.ItemDataRole.UserRole, info.path)
            name_item.setToolTip(info.path)  # 전체 경로 툴팁
            self.file_table.setItem(i, 1, name_item)
            
            # 크기
            size_item = QTableWidgetItem(FileUtils.format_size(info.size))
            size_item.setData(Qt.ItemDataRole.UserRole + 1, info.size)  # 정렬용 숫자 저장
            self.file_table.setItem(i, 2, size_item)
            
            # 청크
            chunk_item = QTableWidgetItem(str(info.chunks))
            chunk_item.setData(Qt.ItemDataRole.UserRole + 1, info.chunks)  # 정렬용 숫자 저장
            self.file_table.setItem(i, 3, chunk_item)
            
            total_size += info.size
            total_chunks += info.chunks
        
        # 정렬 다시 활성화
        self.file_table.setSortingEnabled(True)
        
        self.stats_files.setText(f"📄 {len(infos)}개 파일")
        self.stats_chunks.setText(f"📊 {total_chunks} 청크")
        self.stats_size.setText(f"💾 {FileUtils.format_size(total_size)}")
    
    def _open_selected_file(self):
        """선택된 파일 열기 (정렬과 무관하게 작동)"""
        row = self.file_table.currentRow()
        if row >= 0:
            # 저장된 파일 경로 가져오기
            name_item = self.file_table.item(row, 1)
            if name_item:
                file_path = name_item.data(Qt.ItemDataRole.UserRole)
                if file_path:
                    FileUtils.open_file(file_path)
    
    def _search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        if len(query) < 2:
            self._show_status("⚠️ 검색어는 최소 2자 이상 입력하세요.", "#f59e0b", 2500)
            return
        if not self.qa.vector_store:
            QMessageBox.warning(self, "경고", "문서를 먼저 로드하세요")
            return
        
        # 이전 검색 스레드가 실행 중이면 무시
        if self.worker and self.worker.isRunning():
            return
        
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)  # 검색 중 입력 비활성화
        self._clear_results()
        loading = QLabel("🔍 검색 중...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(loading)
        
        # 검색 시간 측정 시작
        import time
        self._search_start_time = time.time()
        
        worker = SearchThread(self.qa, query, self.k_spin.value(), self.hybrid)
        worker.finished.connect(lambda r: self._on_search_done(r, query))
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.worker = worker
        worker.start()
    
    def _on_search_done(self, result, query):
        import time
        search_time = time.time() - getattr(self, '_search_start_time', time.time())
        
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)  # 검색 완료 후 입력 활성화
        self.worker = None  # 스레드 참조 해제
        self._clear_results()
        
        if not result.success:
            # UI에는 요약을 남기고, 상세(스택트레이스)는 다이얼로그로 제공
            self._show_task_error("검색 오류", result)
            err = QLabel(f"❌ {result.message}")
            err.setStyleSheet("color: #ef4444;")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_layout.addWidget(err)
            return
        
        if not result.data:
            self._show_empty_state("no_results")
            return
        
        self.history.add(query)
        self.last_search_results = result.data  # 내보내기용 저장
        self.last_search_query = query
        
        # 결과 헤더 (검색어 + 통계 + 내보내기 버튼)
        header_frame = QFrame()
        header_frame.setObjectName("card")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        query_label = QLabel(f"🔎 \"{query}\" - {len(result.data)}개 결과")
        query_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(query_label)
        
        # 검색 시간 표시
        time_label = QLabel(f"⏱ {search_time:.2f}초")
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        header_layout.addWidget(time_label)
        
        header_layout.addStretch()
        
        # 내보내기 버튼
        export_btn = QPushButton("📥 내보내기")
        export_btn.setFixedHeight(30)
        export_btn.clicked.connect(self._export_results)
        header_layout.addWidget(export_btn)
        
        self.result_layout.addWidget(header_frame)
        
        # 결과 카드 추가 시 UI 업데이트 일시 중지 (성능 최적화)
        self.result_area.setUpdatesEnabled(False)
        for i, item in enumerate(result.data, 1):
            card = ResultCard(i, item, self._copy_text, self.font_size, query)
            self.result_layout.addWidget(card)
        self.result_area.setUpdatesEnabled(True)
        
        self.search_input.clear()
        self.search_input.setFocus()
    
    def _export_results(self):
        """검색 결과 내보내기"""
        if not hasattr(self, 'last_search_results') or not self.last_search_results:
            QMessageBox.warning(self, "알림", "내보낼 검색 결과가 없습니다.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "검색 결과 내보내기",
            f"검색결과_{self.last_search_query[:20]}.txt",
            "텍스트 파일 (*.txt);;CSV 파일 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            is_csv = file_path.lower().endswith('.csv')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                if is_csv:
                    f.write("순위,점수,파일,내용\n")
                    for i, item in enumerate(self.last_search_results, 1):
                        content = item['content'].replace('"', '""').replace('\n', ' ')
                        f.write(f'{i},{item["score"]:.2f},"{item["source"]}","{content}"\n')
                else:
                    f.write(f"검색어: {self.last_search_query}\n")
                    f.write(f"결과 수: {len(self.last_search_results)}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for i, item in enumerate(self.last_search_results, 1):
                        f.write(f"[결과 {i}] ({int(item['score']*100)}%)\n")
                        f.write(f"파일: {item['source']}\n")
                        f.write("-" * 30 + "\n")
                        f.write(item['content'] + "\n\n")
            
            self._show_status(f"✅ 결과 내보내기 완료: {os.path.basename(file_path)}", "#10b981", 3000)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"내보내기 실패: {e}")
    
    def _clear_results(self):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _copy_text(self, text):
        """텍스트 복사 및 상태 표시"""
        QApplication.clipboard().setText(text)
        self._show_status("✅ 클립보드에 복사됨", "#10b981", 2000)
    
    def _show_status(self, message: str, color: str = "#eaeaea", duration: int = 0):
        """상태 레이블에 메시지 표시 (duration이 0이면 영구 표시)"""
        # 이전 타이머 취소
        if self.status_timer:
            self.status_timer.stop()
            self.status_timer = None
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        
        if duration > 0:
            self.status_timer = QTimer()
            self.status_timer.setSingleShot(True)
            self.status_timer.timeout.connect(lambda: self.status_label.setText(""))
            self.status_timer.start(duration)
    
    def _show_empty_state(self, state_type: str = "welcome"):
        """빈 상태 위젯 표시"""
        self._clear_results()
        
        if state_type == "welcome":
            widget = EmptyStateWidget(
                "👋",
                "사내 규정 검색기",
                "폴더를 선택하고 문서를 로드한 후 검색을 시작하세요.\nCtrl+O로 폴더 열기"
            )
        elif state_type == "no_results":
            widget = EmptyStateWidget(
                "🔍",
                "검색 결과 없음",
                "다른 검색어로 시도해보세요."
            )
        elif state_type == "ready":
            widget = EmptyStateWidget(
                "✅",
                "검색 준비 완료",
                "검색어를 입력하고 Enter를 누르거나 검색 버튼을 클릭하세요."
            )
        else:
            return
        
        self.result_layout.addWidget(widget)
    
    def _show_history_menu(self):
        """검색 히스토리 메뉴 표시"""
        history_items = self.history.get(10)
        
        if not history_items:
            QMessageBox.information(self, "알림", "검색 히스토리가 없습니다.")
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #16213e;
                border: 1px solid #e94560;
                border-radius: 6px;
                padding: 5px;
            }
            QMenu::item {
                background: transparent;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #e94560;
            }
        """)
        
        for query in history_items:
            action = menu.addAction(f"🔍 {query}")
            action.triggered.connect(lambda checked, q=query: self._search_from_history(q))
        
        menu.addSeparator()
        clear_action = menu.addAction("🗑️ 히스토리 삭제")
        clear_action.triggered.connect(self._clear_history)
        
        # 버튼 아래에 메뉴 표시
        menu.exec(self.history_btn.mapToGlobal(self.history_btn.rect().bottomLeft()))
    
    def _search_from_history(self, query: str):
        """히스토리에서 선택한 검색어로 검색"""
        self.search_input.setText(query)
        self._search()
    
    def _update_cache_size_display(self):
        """캐시 사용량 업데이트"""
        cache_path = self.qa.cache_path
        if os.path.exists(cache_path):
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(cache_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError as e:
                        logger.debug(f"캐시 크기 계산 실패(무시): {fp} - {e}")
            self.cache_size_label.setText(f"💾 캐시 사용량: {FileUtils.format_size(total_size)}")
        else:
            self.cache_size_label.setText("💾 캐시 사용량: 0 B")

    def _update_internal_state_display(self):
        """설정 탭의 '내부 상태' 라벨 갱신(진단/디버깅용)."""
        if not hasattr(self, "internal_state_label"):
            return

        data_dir = get_data_directory()
        models_dir = get_models_directory()
        cache_root = self.qa.cache_path

        current_cache_dir = ""
        if self.last_folder and os.path.isdir(self.last_folder):
            try:
                current_cache_dir = self.qa._get_cache_dir(self.last_folder)
            except Exception:
                current_cache_dir = ""

        last_op = getattr(self.qa, "last_op", {}) or {}
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
            # cache_info.json 요약(실패해도 무시)
            try:
                ci_path = os.path.join(current_cache_dir, "cache_info.json")
                if os.path.exists(ci_path):
                    with open(ci_path, "r", encoding="utf-8") as f:
                        ci = json.load(f)
                    schema = ci.get("schema_version", "")
                    files = ci.get("files", {}) or {}
                    total_files = len(files)
                    total_chunks = 0
                    for v in files.values():
                        try:
                            total_chunks += int((v or {}).get("chunks", 0))
                        except (TypeError, ValueError):
                            pass
                    if schema:
                        lines.append(f"📌 cache schema: v{schema}, files: {total_files}, chunks: {total_chunks}")
            except Exception:
                pass
        if last_op_id:
            lines.append(f"📌 last op: {last_op_type}/{last_op_status} ({last_op_id})")

        text = "\n".join(lines)
        self.internal_state_label.setText(text)
        self.internal_state_label.setToolTip(text)

    def _export_diagnostics(self):
        """진단 번들(zip) 내보내기."""
        default_name = f"diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "진단 내보내기",
            default_name,
            "Zip 파일 (*.zip)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"

        result = self.qa.export_diagnostics_zip(file_path)
        self._update_internal_state_display()
        if result.success:
            QMessageBox.information(self, "완료", f"✅ {result.message}\n\n{file_path}")
        else:
            self._show_task_error("진단 내보내기 실패", result)

    def _show_task_error(self, title: str, result: TaskResult, *, icon: QMessageBox.Icon = QMessageBox.Icon.Critical):
        """TaskResult 기반 표준 오류 UI: 요약 + 상세(debug) 보기."""
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)

        summary_lines = [result.message or "작업 실패"]
        if getattr(result, "error_code", ""):
            summary_lines.append(f"(error_code: {result.error_code})")
        if getattr(result, "op_id", ""):
            summary_lines.append(f"(op_id: {result.op_id})")
        msg.setText("\n".join(summary_lines))

        detail_btn = None
        if getattr(result, "debug", ""):
            detail_btn = msg.addButton("상세 보기", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()

        if detail_btn is not None and msg.clickedButton() == detail_btn:
            details_title = f"{title} 상세"
            dlg = DebugDetailsDialog(details_title, result.debug, self)
            dlg.exec()
    
    def _clear_cache(self):
        if QMessageBox.question(self, "확인", "캐시를 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.qa.clear_cache(reset_memory=True)
            self._set_search_controls_enabled(False)
            self.recent_btn.setEnabled(False)
            self._show_empty_state("welcome")
            self._update_file_table()
            self._update_cache_size_display()  # 캐시 크기 업데이트
            self._update_internal_state_display()
            self._show_status("✅ 디스크+메모리 캐시 삭제 완료. 폴더를 다시 로드하세요.", "#10b981", 3500)
    
    def _clear_history(self):
        if QMessageBox.question(self, "확인", "히스토리를 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self._show_status("✅ 히스토리 삭제됨", "#10b981", 3000)
    
    def _update_model_status(self):
        """모델 다운로드 상태 업데이트"""
        cache_dir = get_models_directory()
        if os.path.exists(cache_dir):
            # 캐시 디렉토리의 모델 폴더 수 확인
            model_dirs = [d for d in os.listdir(cache_dir) if os.path.isdir(os.path.join(cache_dir, d))]
            total_models = len(AppConfig.AVAILABLE_MODELS)
            # 모델 캐시 크기 계산
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(cache_dir):
                for f in filenames:
                    try:
                        total_size += os.path.getsize(os.path.join(dirpath, f))
                    except OSError as e:
                        logger.debug(f"모델 크기 계산 실패(무시): {dirpath}\\{f} - {e}")
            msg = f"📦 다운로드된 모델: {FileUtils.format_size(total_size)}"
            self.model_status_label.setText(msg)
            self.model_status_label.setToolTip(f"{msg}\n경로: {cache_dir}")
        else:
            self.model_status_label.setText("📦 다운로드된 모델 없음 (온라인 필요)")
            self.model_status_label.setToolTip(f"경로: {cache_dir}")
    
    def _download_all_models(self):
        """선택된 모델 다운로드 시작"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        
        # 모델 선택 다이얼로그 생성
        dialog = QDialog(self)
        dialog.setWindowTitle("오프라인 모델 다운로드")
        dialog.setMinimumWidth(400)
        dialog_layout = QVBoxLayout(dialog)
        
        # 안내 텍스트
        info_label = QLabel(
            "다운로드할 모델을 선택하세요.\n"
            "각 모델은 약 400MB~1GB입니다.\n"
            "인터넷 연결이 필요하며, 완료 후 오프라인에서 사용할 수 있습니다."
        )
        info_label.setStyleSheet("color: #888; margin-bottom: 10px;")
        dialog_layout.addWidget(info_label)
        
        # 체크박스 생성
        checkboxes = {}
        for name, model_id in AppConfig.AVAILABLE_MODELS.items():
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)  # 기본 선택
            checkbox.setToolTip(f"모델 ID: {model_id}")
            checkboxes[name] = (checkbox, model_id)
            dialog_layout.addWidget(checkbox)
        
        # 전체 선택/해제 버튼
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb, _ in checkboxes.values()])
        btn_row.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("전체 해제")
        deselect_all_btn.clicked.connect(lambda: [cb.setChecked(False) for cb, _ in checkboxes.values()])
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch()
        dialog_layout.addLayout(btn_row)
        
        # 확인/취소 버튼
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)
        
        # 다이얼로그 표시
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        # 선택된 모델 수집
        selected_models = [
            (name, model_id) 
            for name, (checkbox, model_id) in checkboxes.items() 
            if checkbox.isChecked()
        ]
        
        if not selected_models:
            QMessageBox.warning(self, "알림", "선택된 모델이 없습니다.")
            return
        
        # 진행 다이얼로그 표시
        self.progress_dialog = ProgressDialog(self, "모델 다운로드 중")
        dialog_x = self.x() + (self.width() - self.progress_dialog.width()) // 2
        dialog_y = self.y() + (self.height() - self.progress_dialog.height()) // 2
        self.progress_dialog.move(dialog_x, dialog_y)
        self.progress_dialog.show()
        
        # 선택된 모델만 다운로드
        worker = ModelDownloadThread(selected_models)
        worker.progress.connect(self.progress_dialog.update_progress)
        worker.finished.connect(self._on_download_done)
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.progress_dialog.canceled.connect(worker.cancel)
        self.download_worker = worker
        worker.start()
    
    def _on_download_done(self, result):
        """모델 다운로드 완료 핸들러"""
        self._close_progress_dialog()
        self.download_worker = None
        
        self._update_model_status()
        self._update_internal_state_display()
        
        if result.success:
            QMessageBox.information(self, "완료", f"✅ {result.message}")
        else:
            msg = f"❌ {result.message}"
            if result.failed_items:
                msg += "\n\n실패한 모델:\n" + "\n".join(result.failed_items[:5])
            r = TaskResult(
                False,
                msg,
                result.data,
                result.failed_items,
                op_id=getattr(result, "op_id", ""),
                error_code=getattr(result, "error_code", ""),
                debug=getattr(result, "debug", ""),
            )
            self._show_task_error("다운로드 결과", r, icon=QMessageBox.Icon.Warning)
    
    def closeEvent(self, event):
        self._save_config()
        self._close_progress_dialog()
        self._stop_worker_thread(self.worker, "main_worker")
        self._stop_worker_thread(self.download_worker, "download_worker")
        self.worker = None
        self.download_worker = None
        self.qa.cleanup()
        event.accept()
