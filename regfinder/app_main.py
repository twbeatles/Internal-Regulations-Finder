from __future__ import annotations

import sys

_module_name = __name__
from .application import app_main as _impl
from .application.app_main import main

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "app_main", _impl)
