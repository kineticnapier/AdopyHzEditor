"""Compatibility alias for :mod:`desktop.toolbox_fix`."""

import sys as _sys
from desktop import toolbox_fix as _impl

_sys.modules[__name__] = _impl
