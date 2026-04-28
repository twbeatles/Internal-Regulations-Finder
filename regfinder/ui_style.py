from __future__ import annotations

import sys

_module_name = __name__
from .ui import style as _impl
from .ui.style import DARK_STYLE, WINDOWS_UI_FONT_CANDIDATES, get_preferred_ui_font_family, ui_font

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "ui_style", _impl)
