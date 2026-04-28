from __future__ import annotations

import sys

_module_name = __name__
from .core import file_utils as _impl
from .core.file_utils import FileUtils, importlib, os, platform

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "file_utils", _impl)
