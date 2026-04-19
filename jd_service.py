# Backward-compatibility shim — import from services.jd instead
from services.jd import *  # noqa: F401,F403
from services.jd import _score_version_for_jd, _strip_yaml_fences  # noqa: F401
