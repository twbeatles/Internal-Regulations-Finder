from __future__ import annotations

import sys

_module_name = __name__
from .application import workers as _impl
from .application.workers import (
    BaseWorkerThread,
    CacheUsageRefreshThread,
    DocumentProcessorThread,
    ModelDownloadThread,
    ModelLoaderThread,
    SearchThread,
    _import_attr,
    _import_module,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "workers", _impl)
