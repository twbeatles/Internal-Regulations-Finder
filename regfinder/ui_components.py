from __future__ import annotations

import sys

_module_name = __name__
from .ui import components as _impl
from .ui.components import (
    DebugDetailsDialog,
    EmptyStateWidget,
    FileLinkLabel,
    NumericTableWidgetItem,
    PdfPasswordDialog,
    ProgressDialog,
    ResultCard,
    ResultDetailDialog,
    SearchHistory,
    SearchProgressCard,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "ui_components", _impl)
