"""Compatibility alias for :mod:`core.project_io`."""

import sys as _sys
from core import project_io as _impl

_sys.modules[__name__] = _impl
