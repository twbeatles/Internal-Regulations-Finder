from __future__ import annotations

import sys

_module_name = __name__
from .documents import extractor as _impl
from .documents.extractor import (
    BaseOCREngine,
    DocumentExtractor,
    DocumentSegment,
    NoOpOCREngine,
    TesseractOCREngine,
    _import_attr,
    _import_module,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "document_extractor", _impl)
