"""Compatibility alias for :mod:`desktop.midi_import_dialog`."""

import sys as _sys
from desktop import midi_import_dialog as _impl

_sys.modules[__name__] = _impl
