"""Resource bar widget for TunaCode REPL."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from tunacode.constants import RESOURCE_BAR_COST_FORMAT, RESOURCE_BAR_SEPARATOR
from tunacode.types import UserConfig
from tunacode.ui.styles import (
    STYLE_ERROR,
    STYLE_MUTED,
    STYLE_SUCCESS,
    STYLE_WARNING,
)


def _check_lsp_status(user_config: UserConfig) -> tuple[bool, str | None]:
    """Check LSP configuration and server availability.

    Returns:
        Tuple of (is_enabled, server_name_or_none)
    """
    from pathlib import Path

    from tunacode.lsp.servers import get_server_command

    settings = user_config.get("settings", {})
    lsp_config = settings.get("lsp", {})
    is_enabled = lsp_config.get("enabled", False)

    if not is_enabled:
        return False, None

    # Check what server would actually be used for a .py file
    # This reflects the real LSP config, not just what's installed
    command = get_server_command(Path("test.py"))
    if command:
        # Extract server name from command (e.g., "ruff" from ["ruff", "server", "--stdio"])
        binary = command[0]
        # Friendly name mapping
        name_map = {
            "ruff": "ruff",
            "pyright-langserver": "pyright",
            "pylsp": "pylsp",
            "typescript-language-server": "tsserver",
            "gopls": "gopls",
            "rust-analyzer": "rust-analyzer",
        }
        return True, name_map.get(binary, binary)

    return True, None


class ResourceBar(Static):
    """Top bar showing resources: tokens, model, cost, LSP status."""

    def __init__(self) -> None:
        super().__init__("Loading...")
        self._tokens: int = 0
        self._max_tokens: int = 200000
        self._model: str = "---"
        self._cost: float = 0.0
        self._session_cost: float = 0.0
        self._lsp_enabled: bool = False
        self._lsp_server: str | None = None

    def on_mount(self) -> None:
        self._refresh_lsp_status()
        self._refresh_display()

    def _refresh_lsp_status(self) -> None:
        user_config = self._get_user_config()
        if user_config is None:
            return

        self._lsp_enabled, self._lsp_server = _check_lsp_status(user_config)

    def _get_user_config(self) -> UserConfig | None:
        app = getattr(self, "app", None)
        if app is None:
            return None

        state_manager = getattr(app, "state_manager", None)
        if state_manager is None:
            return None

        session = getattr(state_manager, "session", None)
        if session is None:
            return None

        user_config = getattr(session, "user_config", None)
        if user_config is None:
            return None

        return user_config

    def update_stats(
        self,
        *,
        tokens: int | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        cost: float | None = None,
        session_cost: float | None = None,
    ) -> None:
        if tokens is not None:
            self._tokens = tokens
        if max_tokens is not None:
            self._max_tokens = max_tokens
        if model is not None:
            self._model = model
        if cost is not None:
            self._cost = cost
        if session_cost is not None:
            self._session_cost = session_cost
        self._refresh_lsp_status()
        self._refresh_display()

    def _calculate_remaining_pct(self) -> float:
        if self._max_tokens == 0:
            return 0.0
        raw_pct = (self._max_tokens - self._tokens) / self._max_tokens * 100
        return max(0.0, min(100.0, raw_pct))

    def _get_circle_color(self, remaining_pct: float) -> str:
        if remaining_pct > 60:
            return STYLE_SUCCESS
        if remaining_pct > 30:
            return STYLE_WARNING
        return STYLE_ERROR

    def _get_circle_char(self, remaining_pct: float) -> str:
        if remaining_pct > 87.5:
            return "●"
        if remaining_pct > 62.5:
            return "◕"
        if remaining_pct > 37.5:
            return "◑"
        if remaining_pct > 12.5:
            return "◔"
        return "○"

    def _get_lsp_indicator(self) -> tuple[str, str]:
        """Get LSP status indicator character and color.

        Returns:
            Tuple of (indicator_text, style)
        """
        if not self._lsp_enabled:
            return "", STYLE_MUTED  # Don't show anything if LSP is off
        if self._lsp_server:
            return f"LSP: {self._lsp_server}", STYLE_SUCCESS
        return "LSP: no server", STYLE_WARNING

    def _refresh_display(self) -> None:
        sep = RESOURCE_BAR_SEPARATOR
        session_cost_str = RESOURCE_BAR_COST_FORMAT.format(cost=self._session_cost)

        remaining_pct = self._calculate_remaining_pct()
        circle_char = self._get_circle_char(remaining_pct)
        circle_color = self._get_circle_color(remaining_pct)

        lsp_text, lsp_style = self._get_lsp_indicator()

        parts: list[tuple[str, str]] = [
            (circle_char, circle_color),
            (f" {remaining_pct:.0f}%", circle_color),
            (sep, STYLE_MUTED),
            (session_cost_str, STYLE_SUCCESS),
        ]

        # Only show LSP indicator if enabled
        if lsp_text:
            parts.append((sep, STYLE_MUTED))
            parts.append((lsp_text, lsp_style))

        content = Text.assemble(*parts)
        self.update(content)
