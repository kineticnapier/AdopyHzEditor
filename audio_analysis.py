"""Compatibility alias for :mod:`core.audio_analysis`."""

import sys as _sys
from core import audio_analysis as _impl

_sys.modules[__name__] = _impl
