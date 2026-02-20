"""Code discovery tool — unified search replacing glob→grep→read chains.

Model describes what it wants in natural language. The harness extracts search
terms, generates aggressive glob patterns, reads file previews, scores
relevance, and returns a compact typed report.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from tunacode.tools.decorators import base_tool
from tunacode.tools.ignore import IgnoreManager, get_ignore_manager

# ---------------------------------------------------------------------------
# Output types — the ONLY thing the model sees
# ---------------------------------------------------------------------------

MAX_REPORT_FILES = 20
MAX_PREVIEW_LINES = 200
MAX_GLOB_CANDIDATES = 150
MAX_EXCERPT_LINES = 3
MAX_SYMBOLS_PER_FILE = 8
MAX_IMPORTS_PER_FILE = 8

# Extensions we consider source/doc files
SOURCE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".kt", ".scala", ".lua", ".sh", ".bash", ".zsh",
    ".md", ".txt", ".yaml", ".yml", ".toml", ".json", ".ini",
    ".cfg", ".conf", ".sql",
})

# Python keywords that leak into naive symbol extraction
_PYTHON_KEYWORDS = frozenset({
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else",
    "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
    "return", "try", "while", "with", "yield",
})

# JS/TS keywords that leak similarly
_JS_KEYWORDS = frozenset({
    "const", "let", "var", "function", "class", "export", "default",
    "import", "from", "return", "if", "else", "for", "while", "do",
    "switch", "case", "break", "continue", "new", "this", "super",
    "async", "await", "try", "catch", "finally", "throw", "typeof",
    "instanceof", "void", "delete", "in", "of", "yield",
})

_ALL_KEYWORDS = _PYTHON_KEYWORDS | _JS_KEYWORDS


class Relevance(Enum):
    HIGH = "high"
    MEDIUM = "medium"


@dataclass
class FileEntry:
    """A single discovered file with its role in the codebase."""

    path: str
    relevance: Relevance
    role: str
    key_symbols: list[str]
    imports_from: list[str]
    line_count: int = 0
    excerpt: str = ""


@dataclass
class ConceptCluster:
    """Group of files that together implement a concept."""

    name: str
    description: str
    files: list[FileEntry] = field(default_factory=list)


@dataclass
class DiscoveryReport:
    """Compact typed report for model consumption."""

    query: str
    summary: str
    clusters: list[ConceptCluster] = field(default_factory=list)
    file_tree: str = ""
    total_files_scanned: int = 0
    total_candidates: int = 0
    overflow_dirs: list[str] = field(default_factory=list)

    def to_context(self) -> str:
        """Serialize to compact string for model consumption."""
        lines: list[str] = []
        lines.append(f"# Discovery: {self.query}")
        lines.append(self.summary)
        lines.append(
            f"({self.total_files_scanned} scanned → {self.total_candidates} relevant)\n"
        )

        if self.file_tree:
            lines.append("```")
            lines.append(self.file_tree)
            lines.append("```\n")

        for cluster in self.clusters:
            lines.append(f"## {cluster.name}")
            lines.append(f"{cluster.description}\n")
            for f in cluster.files:
                marker = "★" if f.relevance == Relevance.HIGH else "◆"
                lines.append(f"  {marker} `{f.path}` — {f.role} ({f.line_count}L)")
                if f.key_symbols:
                    lines.append(f"    defines: {', '.join(f.key_symbols[:MAX_SYMBOLS_PER_FILE])}")
                if f.imports_from:
                    lines.append(f"    imports: {', '.join(f.imports_from[:MAX_IMPORTS_PER_FILE])}")
                if f.excerpt:
                    lines.append(f"    context: {f.excerpt}")
            lines.append("")

        if self.overflow_dirs:
            lines.append(f"(+{len(self.overflow_dirs)} more in: {', '.join(self.overflow_dirs)})")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Concept expansion — maps root concepts to related filename/content terms
# ---------------------------------------------------------------------------

CONCEPT_EXPANSIONS: dict[str, list[str]] = {
    "auth": ["auth", "login", "session", "token", "jwt", "oauth",
             "credential", "permission", "role", "passport", "sso"],
    "database": ["db", "database", "model", "schema", "migration",
                 "orm", "query", "repository", "entity"],
    "api": ["api", "route", "endpoint", "controller", "handler",
            "middleware", "request", "response"],
    "test": ["test", "spec", "fixture", "mock"],
    "config": ["config", "settings", "env", "constant"],
    "error": ["error", "exception", "fallback", "retry"],
    "cache": ["cache", "redis", "memcache", "store"],
    "queue": ["queue", "worker", "job", "task", "celery"],
    "ontolog": ["ontolog", "relation", "graph", "edge", "node",
                "entity", "schema", "hierarchy", "taxonomy"],
    "type": ["type", "schema", "interface", "protocol", "contract"],
    "tool": ["tool", "command", "action", "executor"],
    "agent": ["agent", "loop", "step", "run", "execute"],
    "ui": ["ui", "widget", "panel", "render", "display", "screen"],
    "prompt": ["prompt", "system", "template", "instruction"],
    "compaction": ["compact", "compaction", "summary", "summarize", "truncate"],
}

_NOISE_WORDS = frozenset({
    "where", "what", "how", "the", "and", "are", "all", "code",
    "related", "find", "show", "module", "file", "defined", "does",
    "this", "that", "which", "with", "for", "from", "about", "look",
    "get", "used", "using", "implement", "implementation",
})


def _extract_search_terms(query: str) -> dict[str, list[str]]:
    """Extract exact identifiers, filename terms, and content terms from natural language."""
    words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", query.lower()))

    # Exact identifiers: CamelCase, snake_case, dotted
    exact: list[str] = re.findall(r"[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+", query)
    exact += re.findall(r"[a-z]+(?:_[a-z]+)+", query)
    exact += re.findall(r"[\w]+\.[\w]+", query)

    filename_terms: list[str] = []
    content_terms: list[str] = []

    for word in words:
        if word in _NOISE_WORDS:
            continue
        matched = False
        for concept, expansions in CONCEPT_EXPANSIONS.items():
            if word.startswith(concept) or concept.startswith(word):
                filename_terms.extend(expansions[:4])
                content_terms.extend(expansions)
                matched = True
                break
        if not matched:
            filename_terms.append(word)
            content_terms.append(word)

    filename_terms = [t for t in filename_terms if t not in _NOISE_WORDS]
    content_terms = [t for t in content_terms if t not in _NOISE_WORDS]

    return {
        "exact": list(dict.fromkeys(exact)),
        "filename": list(dict.fromkeys(filename_terms)),
        "content": list(dict.fromkeys(content_terms)),
    }


# ---------------------------------------------------------------------------
# Glob pattern generation — aggressive, cheap, cast a wide net
# ---------------------------------------------------------------------------

def _detect_dominant_extensions(project_root: Path, sample_limit: int = 300) -> list[str]:
    """Sample the project to find the most common source extensions."""
    ext_counts: dict[str, int] = {}
    count = 0
    for p in project_root.rglob("*"):
        if count >= sample_limit:
            break
        if p.is_file() and p.suffix in SOURCE_EXTENSIONS:
            ext_counts[p.suffix] = ext_counts.get(p.suffix, 0) + 1
            count += 1
    sorted_exts = sorted(ext_counts.items(), key=lambda x: -x[1])
    return [ext for ext, c in sorted_exts if c > 2][:6]


def _generate_glob_patterns(terms: dict[str, list[str]], extensions: list[str]) -> list[str]:
    """Generate 3x+ patterns per filename term: filename, directory, per-extension."""
    patterns: list[str] = []

    for term in terms["filename"]:
        patterns.append(f"**/*{term}*")
        patterns.append(f"**/{term}*/**")
        patterns.append(f"**/*{term}*/**")
        for ext in extensions:
            patterns.append(f"**/*{term}*{ext}")

    return list(dict.fromkeys(patterns))


# ---------------------------------------------------------------------------
# Candidate collection — glob + ignore filtering
# ---------------------------------------------------------------------------

def _collect_candidates(
    patterns: list[str],
    root: Path,
    ignore_manager: IgnoreManager,
    max_candidates: int = MAX_GLOB_CANDIDATES,
) -> list[Path]:
    """Run glob patterns, filter through ignore manager, deduplicate."""
    candidates: dict[str, Path] = {}

    for pattern in patterns:
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            if match.suffix not in SOURCE_EXTENSIONS:
                continue
            if ignore_manager.should_ignore(match):
                continue
            key = str(match.resolve())
            if key not in candidates:
                candidates[key] = match

    result = sorted(candidates.values(), key=lambda p: len(p.parts))
    return result[:max_candidates]


# ---------------------------------------------------------------------------
# Prospect evaluation — read first N lines, score, keep or skip
# ---------------------------------------------------------------------------

@dataclass
class _Prospect:
    path: Path
    keep: bool
    relevance: Relevance
    role: str
    key_symbols: list[str]
    imports: list[str]
    excerpt: str
    line_count: int
    score: float = 0.0


def _evaluate_prospect(
    path: Path,
    terms: dict[str, list[str]],
    max_preview_lines: int = MAX_PREVIEW_LINES,
) -> _Prospect:
    """Read first N lines, score against search terms, decide keep/skip."""
    try:
        text = path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return _empty_prospect(path)

    all_lines = text.splitlines()
    line_count = len(all_lines)
    preview = "\n".join(all_lines[:max_preview_lines])
    preview_lower = preview.lower()

    # --- Scoring ---
    exact_hits = sum(1 for t in terms["exact"] if t in preview)
    content_hits = sum(1 for t in terms["content"] if t.lower() in preview_lower)
    path_lower = str(path).lower()
    filename_hits = sum(1 for t in terms["filename"] if t in path_lower)

    score = (exact_hits * 3.0) + (content_hits * 1.0) + (filename_hits * 2.0)

    # --- Threshold ---
    if exact_hits >= 1 or content_hits >= 3 or (filename_hits >= 2 and content_hits >= 1):
        relevance = Relevance.HIGH
    elif content_hits >= 2 or (filename_hits >= 1 and content_hits >= 1):
        relevance = Relevance.MEDIUM
    else:
        return _empty_prospect(path)

    symbols = _extract_symbols(preview)
    imports = _extract_imports(preview)
    role = _infer_role(path, symbols)
    excerpt = _build_excerpt(all_lines[:max_preview_lines], terms, max_lines=MAX_EXCERPT_LINES)

    return _Prospect(
        path=path, keep=True, relevance=relevance, role=role,
        key_symbols=symbols[:MAX_SYMBOLS_PER_FILE],
        imports=imports[:MAX_IMPORTS_PER_FILE],
        excerpt=excerpt, line_count=line_count, score=score,
    )


def _empty_prospect(path: Path) -> _Prospect:
    return _Prospect(
        path=path, keep=False, relevance=Relevance.MEDIUM,
        role="", key_symbols=[], imports=[], excerpt="", line_count=0,
    )


def _extract_symbols(text: str) -> list[str]:
    """Extract function/class/struct names, filtering out language keywords."""
    symbols: list[str] = []
    # Python
    symbols.extend(re.findall(r"(?:def|class)\s+([a-zA-Z_]\w+)", text))
    # JS/TS
    symbols.extend(re.findall(r"function\s+([a-zA-Z_]\w+)", text))
    symbols.extend(re.findall(r"(?:export\s+)?class\s+([a-zA-Z_]\w+)", text))
    # Go
    for match in re.finditer(r"func\s+(?:\([^)]+\)\s+)?([a-zA-Z_]\w+)", text):
        symbols.append(match.group(1))
    # Rust
    symbols.extend(
        re.findall(r"(?:pub\s+)?(?:fn|struct|enum|trait)\s+([a-zA-Z_]\w+)", text)
    )

    # Deduplicate, filter keywords
    seen: set[str] = set()
    filtered: list[str] = []
    for s in symbols:
        if s not in seen and s not in _ALL_KEYWORDS:
            seen.add(s)
            filtered.append(s)
    return filtered


def _extract_imports(text: str) -> list[str]:
    """Extract import paths from source code."""
    imports: list[str] = []
    imports.extend(re.findall(r"from\s+([\w.]+)\s+import", text))
    imports.extend(re.findall(r"^import\s+([\w.]+)", text, re.MULTILINE))
    imports.extend(re.findall(r'from\s+["\']([^"\']+)["\']', text))
    imports.extend(re.findall(r'require\(["\']([^"\']+)["\']\)', text))
    return list(dict.fromkeys(imports))


def _infer_role(path: Path, symbols: list[str]) -> str:
    """Build a short role description from path and top symbols."""
    parent = path.parent.name if path.parent.name != "." else ""
    name = path.stem
    base = f"{parent}/{name}" if parent else name
    if symbols:
        return f"{base} ({', '.join(symbols[:2])})"
    return base


def _build_excerpt(
    lines: list[str],
    terms: dict[str, list[str]],
    max_lines: int = MAX_EXCERPT_LINES,
) -> str:
    """Pick the most relevant lines as a compact excerpt."""
    all_terms = [t.lower() for t in terms["exact"] + terms["content"]]
    scored: list[tuple[float, int, str]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 5:
            continue
        line_lower = stripped.lower()
        score = float(sum(1 for t in all_terms if t in line_lower))
        # Boost definitions
        if re.match(r"\s*(def |class |function |fn |struct |export )", line):
            score += 0.5
        if score > 0:
            scored.append((score, i, stripped))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_lines]
    top.sort(key=lambda x: x[1])
    return " | ".join(t[2][:120] for t in top)


# ---------------------------------------------------------------------------
# Clustering — group by directory, sort by relevance, cap at MAX_REPORT_FILES
# ---------------------------------------------------------------------------

def _cluster_prospects(
    prospects: list[_Prospect],
) -> tuple[list[ConceptCluster], list[str]]:
    """Group kept prospects by directory.

    Returns (clusters, overflow_dirs) where overflow_dirs lists directories
    whose files were trimmed to stay within MAX_REPORT_FILES.
    """
    kept = [p for p in prospects if p.keep]
    kept.sort(key=lambda x: -x.score)

    dir_groups: dict[str, list[_Prospect]] = {}
    for p in kept:
        key = str(p.path.parent)
        dir_groups.setdefault(key, []).append(p)

    # Build clusters sorted by total high-relevance count
    clusters: list[ConceptCluster] = []
    for dir_path, group in dir_groups.items():
        name = Path(dir_path).name or "root"
        high = sum(1 for p in group if p.relevance == Relevance.HIGH)
        files = [
            FileEntry(
                path=str(p.path),
                relevance=p.relevance,
                role=p.role,
                key_symbols=p.key_symbols,
                imports_from=p.imports,
                line_count=p.line_count,
                excerpt=p.excerpt,
            )
            for p in sorted(group, key=lambda x: -x.score)
        ]
        clusters.append(ConceptCluster(
            name=name,
            description=f"{len(group)} files ({high} high relevance)",
            files=files,
        ))

    clusters.sort(key=lambda c: -sum(1 for f in c.files if f.relevance == Relevance.HIGH))

    # Cap total files at MAX_REPORT_FILES
    total_files = 0
    trimmed_clusters: list[ConceptCluster] = []
    overflow_dirs: list[str] = []

    for cluster in clusters:
        remaining = MAX_REPORT_FILES - total_files
        if remaining <= 0:
            overflow_dirs.append(cluster.name)
            continue
        if len(cluster.files) <= remaining:
            trimmed_clusters.append(cluster)
            total_files += len(cluster.files)
        else:
            overflow_count = len(cluster.files) - remaining
            trimmed = ConceptCluster(
                name=cluster.name,
                description=f"{remaining} of {len(cluster.files)} files shown",
                files=cluster.files[:remaining],
            )
            trimmed_clusters.append(trimmed)
            total_files += remaining
            overflow_dirs.append(f"{cluster.name} (+{overflow_count})")

    return trimmed_clusters, overflow_dirs


def _build_relevant_tree(prospects: list[_Prospect], root: Path) -> str:
    """Build a file tree showing only kept prospects."""
    kept = [p for p in prospects if p.keep]
    if not kept:
        return ""

    resolved_root = root.resolve()
    dirs: set[str] = set()
    file_relevance: dict[str, Relevance] = {}

    for p in kept:
        try:
            rel = str(p.path.resolve().relative_to(resolved_root))
        except ValueError:
            continue
        file_relevance[rel] = p.relevance
        for parent in Path(rel).parents:
            parent_str = str(parent)
            if parent_str != ".":
                dirs.add(parent_str)

    all_paths = sorted(dirs | set(file_relevance.keys()))
    lines: list[str] = []
    for path_str in all_paths:
        depth = path_str.count(os.sep)
        name = Path(path_str).name
        prefix = "  " * depth
        if path_str in file_relevance:
            marker = "★" if file_relevance[path_str] == Relevance.HIGH else "◆"
            lines.append(f"{prefix}{marker} {name}")
        else:
            lines.append(f"{prefix}{name}/")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sync pipeline — runs in a thread to avoid blocking the event loop
# ---------------------------------------------------------------------------

def _discover_sync(query: str, project_root: str) -> DiscoveryReport:
    """Synchronous discovery pipeline. Offloaded to a thread by the async wrapper."""
    root = Path(project_root).resolve()
    ignore_manager = get_ignore_manager(root)

    terms = _extract_search_terms(query)
    extensions = _detect_dominant_extensions(root)
    patterns = _generate_glob_patterns(terms, extensions)
    candidates = _collect_candidates(patterns, root, ignore_manager)

    prospects = [_evaluate_prospect(p, terms) for p in candidates]
    kept = [p for p in prospects if p.keep]

    clusters, overflow_dirs = _cluster_prospects(prospects)
    tree = _build_relevant_tree(prospects, root)

    high = sum(1 for p in kept if p.relevance == Relevance.HIGH)
    med = sum(1 for p in kept if p.relevance == Relevance.MEDIUM)

    cluster_count = len(clusters)
    summary = (
        f"Found {len(kept)} relevant files "
        f"({high} high, {med} medium) in {cluster_count} areas."
    )
    if clusters:
        summary += f" Key: {', '.join(c.name for c in clusters[:3])}."

    return DiscoveryReport(
        query=query,
        summary=summary,
        clusters=clusters,
        file_tree=tree,
        total_files_scanned=len(candidates),
        total_candidates=len(kept),
        overflow_dirs=overflow_dirs,
    )


# ---------------------------------------------------------------------------
# Tool entry point — the one tool the model calls
# ---------------------------------------------------------------------------

@base_tool
async def discover(
    query: str,
    directory: str = ".",
) -> str:
    """Find and map code related to a concept, feature, or module.

    Describe what you're looking for in natural language. Returns a structured
    report of relevant files, their roles, key symbols, and relationships.
    Use INSTEAD of manually chaining glob, grep, and read.

    Args:
        query: What to find, e.g. "where is auth handled",
               "database schema and migrations", "tool registration and execution".
        directory: Project root to search from (default: current directory).

    Returns:
        Compact discovery report with file map, clusters, symbols, and excerpts.
    """
    report = await asyncio.to_thread(_discover_sync, query, directory)
    return report.to_context()
