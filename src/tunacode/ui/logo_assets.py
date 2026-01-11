"""Helpers for loading pre-rendered ANSI logo assets."""

from __future__ import annotations

import importlib.resources as resources

LOGO_ASSETS_DIRNAME = "assets"
LOGO_TEXT_ENCODING = "utf-8"
LOGO_WELCOME_FILENAME = "logo.ansi"
UI_PACKAGE_NAME = "tunacode.ui"


def read_logo_ansi(logo_filename: str) -> str:
    """Load the ANSI logo asset by filename."""
    ui_package_files = resources.files(UI_PACKAGE_NAME)
    assets_dir = ui_package_files.joinpath(LOGO_ASSETS_DIRNAME)
    logo_path = assets_dir.joinpath(logo_filename)
    if not logo_path.is_file():
        raise FileNotFoundError(f"Logo asset not found: {logo_path}")
    return logo_path.read_text(encoding=LOGO_TEXT_ENCODING)
