import logging
import subprocess
from pathlib import Path
from typing import Dict, List

from tunacode.utils.ripgrep import ripgrep
from tunacode.utils.system import list_cwd

logger = logging.getLogger(__name__)


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
    except Exception as e:
        logger.warning(f"Failed to get git status: {e}")
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


async def get_code_style() -> str:
    """Concatenate contents of all AGENTS.md files up the directory tree."""
    parts: List[str] = []
    current = Path.cwd()
    while True:
        file = current / "AGENTS.md"
        if file.exists():
            try:
                parts.append(file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.debug(f"Failed to read AGENTS.md at {file}: {e}")
        if current == current.parent:
            break
        current = current.parent
    return "\n".join(parts)


async def get_claude_files() -> List[str]:
    """Return a list of additional AGENTS.md files in the repo."""
    return ripgrep("AGENTS.md", ".")
