from __future__ import annotations

import sys

_module_name = __name__
from .application import worker_registry as _impl
from .application.worker_registry import WorkerLike, WorkerRegistry

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "worker_registry", _impl)
