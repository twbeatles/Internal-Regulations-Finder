from __future__ import annotations

import sys

_module_name = __name__
from .storage import persistence as _impl
from .storage.persistence import BookmarkStore, ConfigManager, JsonListStore, RecentFoldersStore, SearchLogStore

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "persistence", _impl)
