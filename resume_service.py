# Backward-compatibility shim — import from services.resume instead
from services.resume import *  # noqa: F401,F403
from services.resume import (  # noqa: F401
    get_current_resume, save_current_resume, tag_version,
    list_versions, get_version, restore_version,
    _validate_yaml, parse_yaml, dump_yaml,
)
