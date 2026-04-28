from __future__ import annotations

import sys

_module_name = __name__
from .search import bm25 as _impl
from .search.bm25 import BM25Index

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "bm25", _impl)
