"""Compatibility alias for :mod:`desktop.editor_view`."""

import sys as _sys
from desktop import editor_view as _impl

_sys.modules[__name__] = _impl
