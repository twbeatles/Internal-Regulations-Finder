from __future__ import annotations

import sys

_module_name = __name__
from .search import diagnostics as _impl
from .search.diagnostics import RegulationQADiagnosticsMixin

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "qa_system_mixins", _impl)
