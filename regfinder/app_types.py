from __future__ import annotations

import sys

_module_name = __name__
from .core import types as _impl
from .core.types import (
    AppConfig,
    DiscoveredFile,
    EmbeddingRuntimeState,
    FileInfo,
    FileStatus,
    ModelDownloadState,
    ModelDownloadStateMap,
    SearchHistoryEntry,
    SearchStats,
    TaskResult,
    TaskStatus,
    TextCacheSnapshot,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "app_types", _impl)
