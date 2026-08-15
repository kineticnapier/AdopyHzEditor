"""React/pywebview backend package.

The aliases below keep the moved backend module imports stable during this
structure-only refactor. They are internal compatibility names, not public API.
"""

import sys

from . import editing as _editing
from . import io as _io
from . import notes as _notes

sys.modules.setdefault("web_backend_editing", _editing)
sys.modules.setdefault("web_backend_io", _io)
sys.modules.setdefault("web_backend_notes", _notes)
