from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ProjectAudioPlan:
    accepted: bool
    mode: str
    audio_path: str | None
    relinked: bool = False


def resolve_project_audio_plan(
    audio_path: str | None,
    *,
    notes_only: bool,
    choose_mode: Callable[[str | None], str],
    locate_audio: Callable[[str | None], str | None],
) -> ProjectAudioPlan:
    """Resolve all user choices before either UI commits project state."""
    mode = "skip" if notes_only else str(choose_mode(audio_path))
    if mode == "cancel":
        return ProjectAudioPlan(False, mode, audio_path)
    if mode == "locate":
        located = locate_audio(audio_path)
        if not located:
            return ProjectAudioPlan(False, mode, audio_path)
        return ProjectAudioPlan(True, mode, located, True)
    return ProjectAudioPlan(True, mode, audio_path)
