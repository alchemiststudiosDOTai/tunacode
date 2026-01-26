"""Configuration constants for code indexing."""

from tunacode.utils.system.ignore_patterns import DEFAULT_EXCLUDE_DIRS

IGNORE_DIRS = DEFAULT_EXCLUDE_DIRS

QUICK_INDEX_THRESHOLD = 1000

PRIORITY_DIRS = {"src", "lib", "app", "packages", "core", "internal"}

INDEXED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".md",
    ".rst",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".sql",
    ".graphql",
    ".dockerfile",
    ".containerfile",
    ".gitignore",
    ".env.example",
}
