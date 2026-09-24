"""React/pywebview backend package."""

from .gap_bridge import install_web_gap_bridge
from .track_transcription import install_track_transcription

install_web_gap_bridge()
install_track_transcription()
