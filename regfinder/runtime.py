from __future__ import annotations

import sys

_module_name = __name__
from .core import runtime as _impl
from .core.runtime import (
    OpLoggerAdapter,
    _import_attr,
    _import_module,
    get_app_directory,
    get_config_path,
    get_data_directory,
    get_history_path,
    get_logs_directory,
    get_model_cache_dir_name,
    get_model_cache_path,
    get_models_directory,
    get_op_logger,
    is_model_downloaded,
    logger,
    new_op_id,
    os,
    setup_logger,
    validate_embedding_runtime,
)

globals().update(_impl.__dict__)
sys.modules[_module_name] = _impl
setattr(sys.modules["regfinder"], "runtime", _impl)
