"""Compatibility alias for :mod:`tools.quick_hz`."""

import sys as _sys
from tools import quick_hz as _impl

_sys.modules[__name__] = _impl
