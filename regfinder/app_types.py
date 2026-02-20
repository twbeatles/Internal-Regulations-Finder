# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List

class AppConfig:
    APP_NAME = "사내 규정 검색기"
    APP_VERSION = "9.3"
    
    AVAILABLE_MODELS: Dict[str, str] = {
        "SNU SBERT (고성능)": "snunlp/KR-SBERT-V40K-klueNLI-augSTS",
        "BM-K Simal (균형)": "BM-K/ko-simal-roberta-base",
        "JHGan SBERT (빠름)": "jhgan/ko-sbert-nli"
    }
    DEFAULT_MODEL = "JHGan SBERT (빠름)"
    
    CONFIG_FILE = "config.json"
    HISTORY_FILE = "search_history.json"
    SUPPORTED_EXTENSIONS = ('.txt', '.docx', '.pdf', '.hwp')
    
    MAX_FONT_SIZE = 32
    MIN_FONT_SIZE = 8
    DEFAULT_FONT_SIZE = 14
    DEFAULT_SEARCH_RESULTS = 3
    MAX_SEARCH_RESULTS = 10
    MAX_HISTORY_SIZE = 30
    
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 80
    VECTOR_WEIGHT = 0.7
    BM25_WEIGHT = 0.3
    MAX_DOCS_IN_MEMORY = 5000
    BATCH_SIZE = 100


class TaskStatus(Enum):
    IDLE = auto()
    LOADING_MODEL = auto()
    PROCESSING_DOCS = auto()
    SEARCHING = auto()


class FileStatus(Enum):
    PENDING = "대기"
    PROCESSING = "처리중"
    SUCCESS = "완료"
    FAILED = "실패"
    CACHED = "캐시"


@dataclass
class TaskResult:
    success: bool
    message: str
    data: Any = None
    failed_items: List[str] = field(default_factory=list)
    op_id: str = ""
    error_code: str = ""
    debug: str = ""


@dataclass
class FileInfo:
    path: str
    name: str
    extension: str
    size: int
    status: FileStatus = FileStatus.PENDING
    chunks: int = 0
    error: str = ""
