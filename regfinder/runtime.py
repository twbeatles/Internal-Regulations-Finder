# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import itertools
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from .app_types import AppConfig

def _import_module(module: str):
    try:
        return importlib.import_module(module)
    except Exception as e:
        raise ImportError(f"필수 모듈을 불러올 수 없습니다: {module} ({e})") from e


def _import_attr(module: str, attr: str):
    mod = _import_module(module)
    try:
        return getattr(mod, attr)
    except AttributeError as e:
        raise ImportError(f"모듈 '{module}'에서 '{attr}'를 찾을 수 없습니다") from e

# ============================================================================
# 상수 및 설정
# ============================================================================
_LOG_RECORD_FACTORY = logging.getLogRecordFactory()


def _log_record_factory(*args, **kwargs):
    record = _LOG_RECORD_FACTORY(*args, **kwargs)
    # Formatter에서 항상 %(op_id)s를 사용할 수 있도록 기본값 주입
    if not hasattr(record, "op_id"):
        record.op_id = "-"
    return record


logging.setLogRecordFactory(_log_record_factory)


_OP_COUNTER = itertools.count(1)


def new_op_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}-{os.getpid()}-{next(_OP_COUNTER)}"


class OpLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("op_id", self.extra.get("op_id", "-"))
        return msg, kwargs


def get_op_logger(op_id: Optional[str]) -> logging.LoggerAdapter:
    return OpLoggerAdapter(logger, {"op_id": op_id or "-"})


def get_app_directory() -> str:
    """애플리케이션의 실행 경로 또는 스크립트 경로 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _is_dir_writable(path: str) -> bool:
    """Windows ACL 환경에서도 신뢰 가능한 쓰기 가능 여부 체크(실제 파일 생성/삭제)."""
    try:
        os.makedirs(path, exist_ok=True)
        test_path = os.path.join(path, f".write_test_{os.getpid()}_{int(datetime.now().timestamp())}.tmp")
        with open(test_path, "wb") as f:
            f.write(b"1")
        os.remove(test_path)
        return True
    except Exception:
        return False


def get_data_directory() -> str:
    """
    앱 데이터 저장 루트.
    - 1순위: 실행 폴더(포터블)
    - 2순위: LOCALAPPDATA/APP_NAME
    - 3순위: APPDATA/APP_NAME
    """
    portable = get_app_directory()
    if _is_dir_writable(portable):
        return portable

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    target = os.path.join(base, AppConfig.APP_NAME)
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except Exception:
        # 최후 폴백: 포터블 경로(로그/설정 저장 실패 가능)
        return portable


def get_config_path() -> str:
    return os.path.join(get_data_directory(), AppConfig.CONFIG_FILE)


def get_history_path() -> str:
    return os.path.join(get_data_directory(), AppConfig.HISTORY_FILE)


def get_logs_directory() -> str:
    return os.path.join(get_data_directory(), "logs")


def get_models_directory() -> str:
    return os.path.join(get_data_directory(), "models")


def setup_logger() -> logging.Logger:
    """로깅 환경 설정 (자동 순환 포함)"""
    from logging.handlers import RotatingFileHandler
    
    logger = logging.getLogger('RegSearch')
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    log_dir = get_logs_directory()
    os.makedirs(log_dir, exist_ok=True)
    
    # 파일 로거 (10MB, 3개 파일 순환)
    fh = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] [op:%(op_id)s] %(message)s'))
    logger.addHandler(fh)
    
    # 콘솔 로거 (개발 환경용)
    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] [op:%(op_id)s] %(message)s'))
        logger.addHandler(ch)
         
    return logger

logger = setup_logger()
