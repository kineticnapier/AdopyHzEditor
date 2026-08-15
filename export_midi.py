"""Compatibility alias for :mod:`exporters.midi`."""

import sys as _sys
from exporters import midi as _impl

_sys.modules[__name__] = _impl
