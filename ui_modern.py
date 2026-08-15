"""Compatibility alias for :mod:`desktop.ui_modern`."""

import sys as _sys
from desktop import ui_modern as _impl

_sys.modules[__name__] = _impl
