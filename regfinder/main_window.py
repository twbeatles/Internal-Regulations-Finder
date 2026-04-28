from __future__ import annotations

import sys

_module_name = __name__
from .ui import main_window as _impl
from .ui.main_window import MainWindow

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "main_window", _impl)
