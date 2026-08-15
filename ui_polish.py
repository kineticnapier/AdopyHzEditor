"""Compatibility alias for :mod:`desktop.ui_polish`."""

import sys as _sys
from desktop import ui_polish as _impl

_sys.modules[__name__] = _impl
