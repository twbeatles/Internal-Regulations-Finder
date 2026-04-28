from __future__ import annotations

import sys

_module_name = __name__
from .storage import text_cache as _impl
from .storage.text_cache import CachedChunk, TextCacheReplacement, TextCacheStore

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "text_cache", _impl)
