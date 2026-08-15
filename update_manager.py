"""Compatibility alias for :mod:`desktop.update_manager`."""

import sys as _sys
from desktop import update_manager as _impl

_sys.modules[__name__] = _impl
