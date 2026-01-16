"""Shared syntax highlighting utilities for tool renderers.

Provides language detection from file extensions and consistent
syntax highlighting across all tool viewports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.syntax import Syntax
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import RenderableType

# NeXTSTEP-consistent theme used across all renderers
SYNTAX_THEME = "monokai"

# Map file extensions to pygments lexer names
EXTENSION_LEXERS: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    # JavaScript/TypeScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    # Rust
    ".rs": "rust",
    # Go
    ".go": "go",
    # Java/Kotlin
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    # C/C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    # C#
    ".cs": "csharp",
    # Ruby
    ".rb": "ruby",
    ".rake": "ruby",
    # Shell
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".fish": "fish",
    # Data formats
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".csv": "text",
    # Markup
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    # Database
    ".sql": "sql",
    # Config
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "nginx",
    ".env": "bash",
    # Docker
    "Dockerfile": "docker",
    ".dockerfile": "docker",
    # Make
    "Makefile": "make",
    ".mk": "make",
    # Misc
    ".lua": "lua",
    ".vim": "vim",
    ".php": "php",
    ".swift": "swift",
    ".r": "r",
    ".R": "r",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".scala": "scala",
    ".clj": "clojure",
    ".lisp": "lisp",
    ".el": "lisp",
    ".tex": "latex",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
}


def get_lexer(filepath: str) -> str:
    """Map file extension to pygments lexer name.

    Args:
        filepath: Path to the file (can be relative or absolute)

    Returns:
        Lexer name for syntax highlighting, or "text" if unknown
    """
    path = Path(filepath)
    name = path.name

    # Check for exact filename matches first (Dockerfile, Makefile)
    if name in EXTENSION_LEXERS:
        return EXTENSION_LEXERS[name]

    # Check file extension
    ext = path.suffix.lower()
    return EXTENSION_LEXERS.get(ext, "text")


def syntax_or_text(
    content: str,
    filepath: str | None = None,
    lexer: str | None = None,
    line_numbers: bool = False,
    word_wrap: bool = True,
    start_line: int = 1,
    code_width: int | None = None,
) -> RenderableType:
    """Return Syntax if lexer known, else plain Text.

    Provides consistent syntax highlighting across all tool renderers.
    Falls back gracefully to plain text for unknown file types.

    Args:
        content: The code/text content to render
        filepath: Optional path to detect language from extension
        lexer: Optional explicit lexer override (takes precedence over filepath)
        line_numbers: Whether to show line numbers (default: False)
        word_wrap: Whether to wrap long lines (default: True)
        start_line: Starting line number for line_numbers display

    Returns:
        Syntax object for code, or Text for plain content
    """
    if lexer is None and filepath:
        lexer = get_lexer(filepath)

    # Use Syntax for known languages
    if lexer and lexer != "text":
        return Syntax(
            content,
            lexer,
            theme=SYNTAX_THEME,
            word_wrap=word_wrap,
            line_numbers=line_numbers,
            start_line=start_line,
            code_width=code_width,
        )

    # Fall back to plain text
    return Text(content)


def detect_code_lexer(content: str) -> str | None:
    """Attempt to detect programming language from content heuristics.

    Used for bash output and other cases where we don't have a filepath.
    Returns None if no confident detection.

    Args:
        content: The content to analyze

    Returns:
        Lexer name if detected, None otherwise
    """
    first_line = content.split("\n")[0] if content else ""

    # Shebang detection
    if first_line.startswith("#!"):
        if "python" in first_line:
            return "python"
        if "bash" in first_line or "sh" in first_line:
            return "bash"
        if "node" in first_line:
            return "javascript"
        if "ruby" in first_line:
            return "ruby"
        if "perl" in first_line:
            return "perl"

    # JSON detection
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            import json

            json.loads(stripped)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass

    # Python detection
    python_markers = ["def ", "class ", "import ", "from ", "if __name__"]
    if any(marker in content for marker in python_markers):
        return "python"

    # JavaScript/TypeScript detection
    js_markers = ["function ", "const ", "let ", "var ", "=>", "export ", "import "]
    if any(marker in content for marker in js_markers):
        return "javascript"

    return None
