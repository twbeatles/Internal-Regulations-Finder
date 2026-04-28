from __future__ import annotations

import sys

_module_name = __name__
from .ui import window_mixins as _impl
from .ui.window_mixins import MainWindowConfigMixin, MainWindowInsightsMixin

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "main_window_mixins", _impl)
