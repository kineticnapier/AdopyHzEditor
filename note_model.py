"""Compatibility alias for :mod:`core.note_model`."""

import sys as _sys
from core import note_model as _impl

_sys.modules[__name__] = _impl
