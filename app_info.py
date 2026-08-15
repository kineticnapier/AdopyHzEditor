from __future__ import annotations

from desktop.ui_modern import install_modern_ui
from desktop.ui_final_tweaks import install_final_ui_tweaks

APP_NAME = "AdopyHzEditor"
APP_VERSION = "0.7.2"
GITHUB_REPO = "kineticnapier/AdopyHzEditor"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"

install_final_ui_tweaks()
install_modern_ui()
