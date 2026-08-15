"""Compatibility alias for :mod:`desktop.tile_preview_dialog`."""

import sys as _sys
from desktop import tile_preview_dialog as _impl

_sys.modules[__name__] = _impl
