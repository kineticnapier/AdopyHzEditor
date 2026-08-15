from __future__ import annotations

from app_metadata import (
    APP_NAME,
    APP_VERSION,
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_URL,
    GITHUB_REPO,
)
from desktop.ui_modern import install_modern_ui
from desktop.ui_final_tweaks import install_final_ui_tweaks

install_final_ui_tweaks()
install_modern_ui()
