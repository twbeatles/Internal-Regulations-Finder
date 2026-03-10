# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
)

from .app_types import AppConfig, FileStatus, TaskResult
from .file_utils import FileUtils
from .qa_system import RegulationQASystem
from .runtime import get_models_directory, logger
from .persistence import BookmarkStore, ConfigManager, RecentFoldersStore, SearchLogStore
from .main_window_ui_mixin import MainWindowUIBuilderMixin
from .main_window_mixins import MainWindowConfigMixin, MainWindowInsightsMixin
from .ui_components import (
    EmptyStateWidget,
    ProgressDialog,
    ResultCard,
    SearchHistory,
)
from .worker_registry import WorkerRegistry
from .workers import DocumentProcessorThread, ModelDownloadThread, ModelLoaderThread, SearchThread

class MainWindow(MainWindowUIBuilderMixin, MainWindowInsightsMixin, MainWindowConfigMixin, QMainWindow):

    def __init__(self, qa: RegulationQASystem):
        super().__init__()
        self.qa = qa
        self.config_manager = ConfigManager()
        self.history = SearchHistory()
        self.bookmarks = BookmarkStore()
        self.recents = RecentFoldersStore()
        self.search_logs = SearchLogStore()
        self.workers = WorkerRegistry()
        self.last_folder = ""
        self.model_name = AppConfig.DEFAULT_MODEL
        self.font_size = AppConfig.DEFAULT_FONT_SIZE
        self.hybrid = True
        self.recursive = False
        self.sort_by = "score_desc"
        self.search_filters = {"extension": "", "filename": "", "path": ""}
        self.status_timer = None  # 상태 레이블 타이머 관리
        
        self._load_config()
        self._init_ui()
        self._update_internal_state_display()
        self._refresh_diagnostics_view()
        QTimer.singleShot(100, self._load_model)
    
    def _load_model(self):
        if self.workers.is_running("model"):
            return
        self.status_label.setText("🔄 모델 로딩 중...")
        worker = ModelLoaderThread(self.qa, self.model_name)
        worker.progress.connect(lambda m: self.status_label.setText(f"🔄 {m}"))
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(lambda *_: self.workers.clear("model"))
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.workers.set("model", worker)
        worker.start()
    
    def _on_model_loaded(self, result):
        if result.success:
            self.status_label.setText(f"✅ {result.message}")
            self.status_label.setStyleSheet("color: #10b981;")
            self.folder_btn.setEnabled(True)
            if any(os.path.isdir(p) for p in self.recents.get()):
                self.recent_btn.setEnabled(True)
            self._update_internal_state_display()
            self._refresh_diagnostics_view()
        else:
            self.status_label.setText(f"❌ {result.message}")
            self.status_label.setStyleSheet("color: #ef4444;")
            self._update_internal_state_display()
            self._refresh_diagnostics_view()
            self._show_task_error("모델 로드 오류", result)
    
    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "규정 폴더 선택")
        if folder:
            self._load_folder(folder)
    
    def _load_recent(self):
        folders = [p for p in self.recents.get() if os.path.isdir(p)]
        if not folders:
            QMessageBox.information(self, "알림", "최근 폴더가 없습니다.")
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
                padding: 8px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected { background: #e94560; }
        """)
        for folder in folders:
            action = menu.addAction(f"📂 {folder}")
            if action is not None:
                action.triggered.connect(lambda checked=False, p=folder: self._load_folder(p))
        menu.addSeparator()
        clear_action = menu.addAction("🗑️ 최근 폴더 비우기")
        if clear_action is not None:
            clear_action.triggered.connect(self._clear_recent_folders)
        menu.exec(self.recent_btn.mapToGlobal(self.recent_btn.rect().bottomLeft()))
    
    def _refresh(self):
        if self.last_folder:
            try:
                cache = self.qa.get_cache_dir_for_folder(self.last_folder)
                shutil.rmtree(cache, ignore_errors=True)
            except Exception:
                pass
            self._load_folder(self.last_folder)
    
    def _reload_model(self):
        """모델 즉시 변경"""
        if QMessageBox.question(
            self, "확인",
            "모델을 변경하면 현재 로드된 문서 인덱스가 초기화됩니다.\n계속하시겠습니까?"
        ) == QMessageBox.StandardButton.Yes:
            # 기존 인덱스 초기화
            self.qa.vector_store = None
            self.qa.documents.clear()
            self.qa.doc_meta.clear()
            self.qa.doc_ids.clear()
            if self.qa.bm25:
                self.qa.bm25.clear()
            
            # UI 초기화
            self.search_input.setEnabled(False)
            self.search_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self._show_empty_state("welcome")
            self.file_table.setRowCount(0)
            
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
        if self.workers.is_running("docs"):
            return
        try:
            # 하위 폴더 포함 여부 확인
            recursive_enabled = self.recursive_check.isChecked() if hasattr(self, "recursive_check") else self.recursive
            if recursive_enabled:
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
        
        self.folder_label.setText(folder)
        self.folder_label.setToolTip(folder)
        self.folder_btn.setEnabled(False)
        
        self.progress_dialog = ProgressDialog(self, "문서 처리 중")
        # 부모 윈도우 중앙에 정확히 배치
        dialog_x = self.x() + (self.width() - self.progress_dialog.width()) // 2
        dialog_y = self.y() + (self.height() - self.progress_dialog.height()) // 2
        self.progress_dialog.move(dialog_x, dialog_y)
        self.progress_dialog.show()
        
        worker = DocumentProcessorThread(self.qa, folder, files)
        worker.progress.connect(self.progress_dialog.update_progress)
        worker.finished.connect(lambda r: self._on_folder_done(r, folder))
        worker.finished.connect(lambda *_: self.workers.clear("docs"))
        worker.finished.connect(lambda *_: worker.deleteLater())
        # 취소 시그널 연결
        self.progress_dialog.canceled.connect(worker.cancel)
        self.workers.set("docs", worker)
        worker.start()
    
    def _on_folder_done(self, result, folder):
        """폴더 처리 완료 핸들러"""
        self.progress_dialog.close()
        self.progress_dialog.deleteLater()  # 위젯 메모리 해제
        self.folder_btn.setEnabled(True)
        
        if result.success:
            self.last_folder = folder
            self.recents.add(folder)
            self._save_config()
            self.search_input.setEnabled(True)
            self.search_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
            self.recent_btn.setEnabled(True)
            self._update_file_table()
            self._update_cache_size_display()
            self._update_internal_state_display()
            self._refresh_diagnostics_view()
            self._show_empty_state("ready")
            
            # 상태 표시
            self._show_status(f"✅ {result.message} (청크: {result.data.get('chunks', 0)})", "#10b981")
            self.search_input.setFocus()
            
            # 처리 실패 파일이 있으면 알림
            if result.failed_items:
                failed_count = len(result.failed_items)
                failed_list = "\n".join(result.failed_items[:5])  # 최대 5개만 표시
                more_msg = f"\n...외 {failed_count - 5}개" if failed_count > 5 else ""
                QMessageBox.warning(
                    self, 
                    "일부 파일 처리 실패",
                    f"{failed_count}개 파일 처리 실패:\n\n{failed_list}{more_msg}"
                )
        else:
            self._show_status(f"❌ {result.message}", "#ef4444")
            self._update_internal_state_display()
            self._refresh_diagnostics_view()
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
        if not self.qa.vector_store:
            QMessageBox.warning(self, "경고", "문서를 먼저 로드하세요")
            return
        
        # 이전 검색 스레드가 실행 중이면 무시
        if self.workers.is_running("search"):
            return

        filters = self._gather_search_filters()
        sort_by = self.sort_combo.currentData() if hasattr(self, "sort_combo") else self.sort_by
        self.sort_by = sort_by
        self.search_filters = filters
        self._save_config()
        
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)  # 검색 중 입력 비활성화
        self._clear_results()
        loading = QLabel("🔍 검색 중...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(loading)
        
        # 검색 시간 측정 시작
        import time
        self._search_start_time = time.time()
        
        worker = SearchThread(self.qa, query, self.k_spin.value(), self.hybrid, filters=filters, sort_by=sort_by)
        worker.finished.connect(lambda r: self._on_search_done(r, query))
        worker.finished.connect(lambda *_: self.workers.clear("search"))
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.workers.set("search", worker)
        worker.start()
    
    def _on_search_done(self, result, query):
        import time
        search_time = time.time() - getattr(self, '_search_start_time', time.time())
        elapsed_ms = int(search_time * 1000)
        
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)  # 검색 완료 후 입력 활성화
        self._clear_results()
        self.search_logs.add(
            query=query,
            elapsed_ms=elapsed_ms,
            result_count=len(result.data or []) if result.success else 0,
            success=bool(result.success),
            error_code=getattr(result, "error_code", ""),
        )
        self._refresh_diagnostics_view()
        
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
            card = ResultCard(i, item, self._copy_text, self._add_bookmark, self.font_size, query)
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
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
    
    def _copy_text(self, text):
        """텍스트 복사 및 상태 표시"""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            logger.warning("클립보드가 초기화되지 않았습니다")
            return
        clipboard.setText(text)
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
            if action is not None:
                action.triggered.connect(lambda checked, q=query: self._search_from_history(q))
        
        menu.addSeparator()
        clear_action = menu.addAction("🗑️ 히스토리 삭제")
        if clear_action is not None:
            clear_action.triggered.connect(self._clear_history)
        
        # 버튼 아래에 메뉴 표시
        menu.exec(self.history_btn.mapToGlobal(self.history_btn.rect().bottomLeft()))
    
    def _search_from_history(self, query: str):
        """히스토리에서 선택한 검색어로 검색"""
        self.search_input.setText(query)
        self._search()
    
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
        self._refresh_diagnostics_view()
        if result.success:
            QMessageBox.information(self, "완료", f"✅ {result.message}\n\n{file_path}")
        else:
            self._show_task_error("진단 내보내기 실패", result)

    def _clear_cache(self):
        if QMessageBox.question(self, "확인", "캐시를 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.qa.clear_cache()
            self._update_cache_size_display()  # 캐시 크기 업데이트
            self._update_internal_state_display()
            self._refresh_diagnostics_view()
            self._show_status("✅ 캐시 삭제됨", "#10b981", 3000)
    
    def _clear_history(self):
        if QMessageBox.question(self, "확인", "히스토리를 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self._refresh_diagnostics_view()
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
        if self.workers.is_running("download"):
            return
        
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
        worker.finished.connect(lambda *_: self.workers.clear("download"))
        worker.finished.connect(lambda *_: worker.deleteLater())
        self.progress_dialog.canceled.connect(worker.cancel)
        self.workers.set("download", worker)
        worker.start()
    
    def _on_download_done(self, result):
        """모델 다운로드 완료 핸들러"""
        self.progress_dialog.close()
        self.progress_dialog.deleteLater()
        
        self._update_model_status()
        self._update_internal_state_display()
        self._refresh_diagnostics_view()
        
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
    
    def closeEvent(self, a0: QCloseEvent | None):
        self.workers.cancel_all()
        progress_dialog = getattr(self, "progress_dialog", None)
        if progress_dialog is not None:
            progress_dialog.close()
            progress_dialog.deleteLater()
        self._save_config()
        self.qa.cleanup()
        if a0 is not None:
            a0.accept()
