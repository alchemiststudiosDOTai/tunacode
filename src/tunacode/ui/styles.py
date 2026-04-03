"""Rich-compatible style constants for TunaCode UI.

Centralizes color references to UI_COLORS for consistent theming.
"""

from tunacode.constants import UI_COLORS

# Rich Text style strings (single colors)
STYLE_PRIMARY = UI_COLORS["primary"]
STYLE_ACCENT = UI_COLORS["accent"]
STYLE_SUCCESS = UI_COLORS["success"]
STYLE_WARNING = UI_COLORS["warning"]
STYLE_ERROR = UI_COLORS["error"]
STYLE_MUTED = UI_COLORS["muted"]

# Composite styles
STYLE_HEADING = f"bold {STYLE_ACCENT}"
STYLE_SUBHEADING = f"bold {STYLE_PRIMARY}"
