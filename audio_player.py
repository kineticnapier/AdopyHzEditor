"""Compatibility alias for :mod:`core.audio_player`."""

import sys as _sys
from core import audio_player as _impl

_sys.modules[__name__] = _impl
