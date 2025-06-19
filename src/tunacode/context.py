import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from tunacode.ui.decorators import create_sync_wrapper

from tunacode.utils.ripgrep import ripgrep
from tunacode.utils.system import list_cwd


async def get_git_status() -> Dict[str, object]:
    """Return git branch and dirty state information."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--branch"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        lines = result.stdout.splitlines()
        branch_line = lines[0][2:] if lines else ""
        branch = branch_line.split("...")[0]
        ahead = behind = 0
        if "[" in branch_line and "]" in branch_line:
            bracket = branch_line.split("[", 1)[1].split("]", 1)[0]
            for part in bracket.split(","):
                if "ahead" in part:
                    ahead = int(part.split("ahead")[1].strip().strip(" ]"))
                if "behind" in part:
                    behind = int(part.split("behind")[1].strip().strip(" ]"))
        dirty = any(line for line in lines[1:])
        return {"branch": branch, "ahead": ahead, "behind": behind, "dirty": dirty}
    except Exception:
        return {}


async def get_directory_structure(max_depth: int = 3) -> str:
    """Return a simple directory tree string."""
    files = list_cwd(max_depth=max_depth)
    lines: List[str] = []
    for path in files:
        depth = path.count("/")
        indent = "  " * depth
        name = path.split("/")[-1]
        lines.append(f"{indent}{name}")
    return "\n".join(lines)


_code_style_cache: Optional[str] = None


@create_sync_wrapper
async def get_code_style() -> str:
    """Concatenate contents of all TUNACODE.md files up the directory tree."""
    global _code_style_cache
    if _code_style_cache is not None:
        return _code_style_cache

    parts: List[str] = []
    current = Path.cwd()
    while True:
        file = current / "TUNACODE.md"
        if file.exists():
            try:
                parts.append(file.read_text(encoding="utf-8"))
            except Exception:
                pass
        if current == current.parent:
            break
        current = current.parent

    _code_style_cache = "\n".join(parts)
    return _code_style_cache


async def get_claude_files() -> List[str]:
    """Return a list of additional TUNACODE.md files in the repo."""
    return ripgrep("TUNACODE.md", ".")


async def get_context() -> Dict[str, object]:
    """Gather repository context."""
    git = await get_git_status()
    directory = await get_directory_structure()
    style = await get_code_style()
    claude_files = await get_claude_files()
    return {
        "git": git,
        "directory": directory,
        "codeStyle": style,
        "claudeFiles": claude_files,
    }
