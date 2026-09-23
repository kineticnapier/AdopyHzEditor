"""React/pywebview backend package."""

from .gap_bridge import install_web_gap_bridge
from .vorbis_spectrum_import import install_vorbis_spectrum_import

install_web_gap_bridge()
install_vorbis_spectrum_import()
