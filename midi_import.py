"""Compatibility alias for :mod:`importers.midi`."""

import sys as _sys
from importers import midi as _impl

_sys.modules[__name__] = _impl
