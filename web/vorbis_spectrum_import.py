"""Wire literal Vorbis spectrum import into the existing experimental Web mode."""

from __future__ import annotations

from core.vorbis_spectrum_import import analyze_vorbis_spectrum_notes


def install_vorbis_spectrum_import() -> None:
    """Use spectrum-bin transport for Web's existing Vorbis Direct action.

    Keep the backend/UI surface stable while replacing the experimental
    peak/tracking interpretation with literal spectrum transfer.
    """

    from web import backend

    backend.analyze_vorbis_direct_notes = analyze_vorbis_spectrum_notes
