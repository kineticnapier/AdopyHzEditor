"""Compatibility alias for :mod:`desktop.ui_final_tweaks`."""

import sys as _sys
from desktop import ui_final_tweaks as _impl

_sys.modules[__name__] = _impl
