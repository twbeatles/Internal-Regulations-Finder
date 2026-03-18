# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import itertools
import logging
import os
import sys
from datetime import datetime
from types import ModuleType
from typing import Any, Callable, MutableMapping, Optional

from .app_types import AppConfig, EmbeddingRuntimeState


def _import_module(module: str) -> ModuleType:
    try:
        return importlib.import_module(module)
    except Exception as e:
        raise ImportError(f"필수 모듈을 불러올 수 없습니다: {module} ({e})") from e


def _import_attr(module: str, attr: str) -> Any:
    mod = _import_module(module)
    try:
        return getattr(mod, attr)
    except AttributeError as e:
        raise ImportError(f"모듈 '{module}'에서 '{attr}'를 찾을 수 없습니다") from e

_OP_COUNTER = itertools.count(1)


def new_op_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}-{os.getpid()}-{next(_OP_COUNTER)}"


class OpLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: object, kwargs: MutableMapping[str, Any]) -> tuple[object, MutableMapping[str, Any]]:
        raw_extra = kwargs.get("extra")
        extra: dict[str, Any]
        if isinstance(raw_extra, dict):
            extra = raw_extra
        else:
            extra = {}
            kwargs["extra"] = extra

        adapter_extra = self.extra if isinstance(self.extra, dict) else {}
        extra.setdefault("op_id", adapter_extra.get("op_id", "-"))
        return msg, kwargs


def get_op_logger(op_id: Optional[str]) -> logging.LoggerAdapter:
    return OpLoggerAdapter(logger, {"op_id": op_id or "-"})


def get_app_directory() -> str:
    """애플리케이션 실행 루트 경로 반환."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    try:
        entry = sys.argv[0] if sys.argv else ""
        if entry:
            abs_entry = os.path.abspath(entry)
            if os.path.isfile(abs_entry):
                return os.path.dirname(abs_entry)
            if os.path.isdir(abs_entry):
                return abs_entry
    except Exception:
        pass
    return os.getcwd()


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


def get_model_cache_dir_name(model_id: str) -> str:
    normalized = str(model_id or "").strip().strip("/")
    if not normalized:
        return ""
    return f"models--{normalized.replace('/', '--')}"


def get_model_cache_path(model_id: str, models_dir: Optional[str] = None) -> str:
    base_dir = models_dir or get_models_directory()
    cache_dir_name = get_model_cache_dir_name(model_id)
    return os.path.join(base_dir, cache_dir_name) if cache_dir_name else base_dir


def is_model_downloaded(model_id: str, models_dir: Optional[str] = None) -> bool:
    model_cache_path = get_model_cache_path(model_id, models_dir=models_dir)
    if not os.path.isdir(model_cache_path):
        return False

    blobs_dir = os.path.join(model_cache_path, "blobs")
    snapshots_dir = os.path.join(model_cache_path, "snapshots")
    if not os.path.isdir(blobs_dir) or not os.path.isdir(snapshots_dir):
        return False

    try:
        has_blob = any(entry.is_file() for entry in os.scandir(blobs_dir))
    except OSError:
        has_blob = False

    try:
        has_snapshot = any(entry.is_dir() for entry in os.scandir(snapshots_dir))
    except OSError:
        has_snapshot = False

    return has_blob and has_snapshot


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
    fmt = '%(asctime)s - %(levelname)s - [%(threadName)s] [op:%(op_id)s] %(message)s'
    fh.setFormatter(logging.Formatter(fmt, defaults={"op_id": "-"}))
    logger.addHandler(fh)
    
    # 콘솔 로거 (개발 환경용)
    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(fmt, defaults={"op_id": "-"}))
        logger.addHandler(ch)
         
    return logger

logger = setup_logger()

_EMBEDDING_RUNTIME_STATE = EmbeddingRuntimeState()


def validate_embedding_runtime(
    import_module: Callable[[str], ModuleType] = _import_module,
) -> EmbeddingRuntimeState:
    use_cache = import_module is _import_module
    if use_cache and _EMBEDDING_RUNTIME_STATE.checked:
        if not _EMBEDDING_RUNTIME_STATE.available:
            raise ImportError(_EMBEDDING_RUNTIME_STATE.error)
        return _EMBEDDING_RUNTIME_STATE

    state = _EMBEDDING_RUNTIME_STATE if use_cache else EmbeddingRuntimeState()
    try:
        import_module("PIL.Image")
    except Exception as e:
        state.checked = True
        state.available = False
        state.error = f"Pillow import 실패: {e}"
        raise ImportError(state.error) from e
    try:
        import_module("sklearn.metrics.pairwise")
    except Exception as e:
        state.checked = True
        state.available = False
        state.error = f"scikit-learn import 실패: {e}"
        raise ImportError(state.error) from e
    try:
        import_module("sentence_transformers")
    except Exception as e:
        state.checked = True
        state.available = False
        state.error = f"sentence_transformers import 실패: {e}"
        raise ImportError(state.error) from e

    state.checked = True
    state.available = True
    state.error = ""
    return state
