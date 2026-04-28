from __future__ import annotations

import sys

_module_name = __name__
from .search import text as _impl
from .search.text import (
    bm25_terms,
    highlight_spans,
    highlight_terms,
    matches_path_filter,
    matches_text_filter,
    normalize_compact_text,
    normalize_path_text,
    normalize_search_text,
    repeated_title_text,
    semantic_terms,
    unique_terms,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "search_text", _impl)
