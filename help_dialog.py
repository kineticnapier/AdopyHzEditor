"""Compatibility alias for :mod:`desktop.help_dialog`."""

import sys as _sys
from desktop import help_dialog as _impl

_sys.modules[__name__] = _impl
