"""Compatibility alias for :mod:`exporters.adofai`."""

import sys as _sys
from exporters import adofai as _impl

_sys.modules[__name__] = _impl
