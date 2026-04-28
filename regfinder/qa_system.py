from __future__ import annotations

import sys

_module_name = __name__
from .search import qa_system as _impl
from .search.qa_system import IndexingCanceled, RegulationQASystem, _import_attr, _import_module

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "qa_system", _impl)
