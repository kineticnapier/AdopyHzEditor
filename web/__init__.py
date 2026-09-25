"""React/pywebview backend package."""

from .gap_bridge import install_web_gap_bridge
from .track_display import install_frequency_track_display_policy
from .track_transcription import install_track_transcription

install_web_gap_bridge()
install_track_transcription()
install_frequency_track_display_policy()
