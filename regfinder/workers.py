# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from .app_types import AppConfig, TaskResult
from .runtime import _import_attr, _import_module, get_models_directory, get_op_logger, new_op_id

class BaseWorkerThread(QThread):
    """작업 스레드 공통 베이스: op_id/취소/예외->TaskResult 변환."""

    def __init__(self, op_prefix: str):
        super().__init__()
        self._canceled = False
        self.op_id = new_op_id(op_prefix)
        self._started_at = datetime.now()

    def cancel(self):
        self._canceled = True

    def is_canceled(self) -> bool:
        return self._canceled

    def elapsed_ms(self) -> int:
        try:
            return int((datetime.now() - self._started_at).total_seconds() * 1000)
        except Exception:
            return 0

    def _fail(self, message: str, error_code: str) -> TaskResult:
        return TaskResult(
            False,
            message,
            op_id=self.op_id,
            error_code=error_code,
            debug=traceback.format_exc(),
        )


class ModelLoaderThread(BaseWorkerThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    
    def __init__(self, qa, model_name):
        super().__init__("MODEL")
        self.qa = qa
        self.model_name = model_name
    
    def run(self):
        try:
            result = self.qa.load_model(self.model_name, lambda msg: self.progress.emit(msg), op_id=self.op_id)
        except Exception:
            result = self._fail("모델 로드 중 오류가 발생했습니다", "MODEL_LOAD_FAIL")
        self.finished.emit(result)


class ModelDownloadThread(BaseWorkerThread):
    """선택된 모델을 오프라인 사용을 위해 다운로드"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    
    def __init__(self, selected_models: List[Tuple[str, str]] = None):
        super().__init__("DOWNLOAD")
        # 선택된 모델 리스트, 없으면 전체
        self.models = selected_models or list(AppConfig.AVAILABLE_MODELS.items())

    def _run_download_subprocess(self, model_id: str, cache_dir: str, device: str) -> int:
        script = (
            "import sys\n"
            "from langchain_huggingface import HuggingFaceEmbeddings\n"
            "model_id = sys.argv[1]\n"
            "cache_dir = sys.argv[2]\n"
            "device = sys.argv[3]\n"
            "_ = HuggingFaceEmbeddings(\n"
            "    model_name=model_id,\n"
            "    cache_folder=cache_dir,\n"
            "    model_kwargs={'device': device},\n"
            "    encode_kwargs={'normalize_embeddings': True},\n"
            ")\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script, model_id, cache_dir, device],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=dict(os.environ),
        )
        while proc.poll() is None:
            if self.is_canceled():
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                return -1
            time.sleep(0.3)
        return int(proc.returncode or 0)

    def _run_download_in_process(self, model_id: str, cache_dir: str, device: str):
        HuggingFaceEmbeddings = _import_attr("langchain_huggingface", "HuggingFaceEmbeddings")
        _ = HuggingFaceEmbeddings(
            model_name=model_id,
            cache_folder=cache_dir,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
    
    def run(self):
        try:
            torch = _import_module("torch")
            
            # 네트워크 타임아웃 설정 (5분)
            os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'
            
            cache_dir = get_models_directory()
            os.makedirs(cache_dir, exist_ok=True)
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            total = len(self.models)
            downloaded = []
            failed = []
            
            for i, (name, model_id) in enumerate(self.models):
                if self.is_canceled():
                    self.finished.emit(TaskResult(False, "다운로드 취소됨", op_id=self.op_id, error_code="DOWNLOAD_CANCELED"))
                    return
                
                percent = int((i / total) * 100)
                self.progress.emit(percent, f"다운로드 중: {name}")
                
                try:
                    if getattr(sys, "frozen", False):
                        # onefile 환경에서는 sys.executable -c 실행이 불가능할 수 있어 in-process 폴백
                        if self.is_canceled():
                            self.finished.emit(TaskResult(False, "다운로드 취소됨", op_id=self.op_id, error_code="DOWNLOAD_CANCELED"))
                            return
                        self._run_download_in_process(model_id, cache_dir, device)
                    else:
                        ret = self._run_download_subprocess(model_id, cache_dir, device)
                        if ret == -1:
                            self.finished.emit(TaskResult(False, "다운로드 취소됨", op_id=self.op_id, error_code="DOWNLOAD_CANCELED"))
                            return
                        if ret != 0:
                            raise RuntimeError(f"서브프로세스 종료 코드: {ret}")
                    downloaded.append(name)
                    get_op_logger(self.op_id).info(f"모델 다운로드 완료: {name}")
                except Exception as e:
                    failed.append(f"{name}: {e}")
                    get_op_logger(self.op_id).error(f"모델 다운로드 실패: {name} - {e}")
            
            self.progress.emit(100, "완료!")
            
            if failed:
                self.finished.emit(TaskResult(
                    False, 
                    f"{len(downloaded)}개 성공, {len(failed)}개 실패",
                    {'downloaded': downloaded},
                    failed,
                    op_id=self.op_id,
                    error_code="DOWNLOAD_PARTIAL_FAIL",
                ))
            else:
                self.finished.emit(TaskResult(
                    True,
                    f"모델 다운로드 완료 ({len(downloaded)}개)",
                    {'downloaded': downloaded, 'cache_dir': cache_dir},
                    op_id=self.op_id,
                ))
                
        except Exception as e:
            get_op_logger(self.op_id).exception("모델 다운로드 중 오류")
            self.finished.emit(self._fail(f"다운로드 오류: {e}", "DOWNLOAD_FAIL"))


class DocumentProcessorThread(BaseWorkerThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    
    def __init__(
        self,
        qa,
        folder,
        files,
        pdf_passwords: Optional[Dict[str, str]] = None,
        ocr_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("DOCS")
        self.qa = qa
        self.folder = folder
        self.files = files
        self.pdf_passwords = dict(pdf_passwords or {})
        self.ocr_options = dict(ocr_options or {})
    
    def run(self):
        try:
            result = self.qa.process_documents(
                self.folder,
                self.files,
                lambda p, m: self.progress.emit(p, m),
                cancel_check=self.is_canceled,
                op_id=self.op_id,
                pdf_passwords=self.pdf_passwords,
                ocr_options=self.ocr_options,
            )
        except Exception:
            result = self._fail("문서 처리 중 오류가 발생했습니다", "DOC_PROCESS_FAIL")
        self.finished.emit(result)


class SearchThread(BaseWorkerThread):
    finished = pyqtSignal(object)
    
    def __init__(self, qa, query, k, hybrid):
        super().__init__("SEARCH")
        self.qa = qa
        self.query = query
        self.k = k
        self.hybrid = hybrid
    
    def run(self):
        if self.is_canceled():
            self.finished.emit(TaskResult(False, "검색이 취소되었습니다", op_id=self.op_id, error_code="SEARCH_CANCELED"))
            return
        try:
            result = self.qa.search(self.query, self.k, self.hybrid, op_id=self.op_id)
        except Exception:
            result = self._fail("검색 중 오류가 발생했습니다", "SEARCH_FAIL")
        self.finished.emit(result)
