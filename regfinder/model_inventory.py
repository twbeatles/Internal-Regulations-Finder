from __future__ import annotations

import sys

_module_name = __name__
from .storage import model_inventory as _impl
from .storage.model_inventory import ModelInventory

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "model_inventory", _impl)
