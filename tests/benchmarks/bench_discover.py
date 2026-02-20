"""Real-repo benchmark for discover vs a legacy multi-tool search chain.

This benchmark runs on the TunaCode repository itself and compares:

- discover (single tool call with structured report)
- legacy chain (list_dir -> glob -> grep -> read_file previews)

It measures:
- latency (cold + warm)
- tool-call count
- output token footprint (character-based estimate)
- file recall against hand-labeled expectations
- symbol recall against hand-labeled expectations
- actionability (can the next file be chosen immediately)

Usage:
    uv run python tests/benchmarks/bench_discover.py
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tinyagent import AgentTool

from tunacode.tools.cache_accessors.ignore_manager_cache import clear_ignore_manager_cache
from tunacode.tools.cache_accessors.ripgrep_cache import clear_ripgrep_cache
from tunacode.tools.cache_accessors.xml_prompts_cache import clear_xml_prompts_cache
from tunacode.tools.decorators import base_tool, to_tinyagent_tool
from tunacode.tools.discover import _extract_search_terms, discover
from tunacode.tools.ignore import get_ignore_manager
from tunacode.tools.read_file import read_file
from tunacode.tools.utils.ripgrep import RipgrepExecutor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

MODE_COLD = "cold"
MODE_WARM = "warm"

COLD_RUNS_PER_QUERY = 1
WARM_RUNS_PER_QUERY = 2

TOKEN_CHARS_PER_TOKEN = 4.0
PERCENTILE_P50 = 0.50
PERCENTILE_P95 = 0.95

ACTIONABLE_TOP_FILE_RANK = 3
ACTIONABLE_SYMBOL_RECALL_THRESHOLD = 0.50

LEGACY_LIST_MAX_FILES = 250
LEGACY_GLOB_MAX_FILES = 400
LEGACY_GREP_MAX_MATCHES = 200
LEGACY_GREP_TERM_LIMIT = 8
LEGACY_READ_FILE_LIMIT = 3
LEGACY_READ_LINE_LIMIT = 120

BENCH_TOOL_CALL_ID = "bench-call-id"

HIDDEN_PREFIX = "."

SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".md",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
    }
)

DISCOVER_FILE_PATTERN = re.compile(r"[★◆]\s+`([^`]+)`")
DISCOVER_DEFINES_PATTERN = re.compile(r"defines:\s*(.+)")

SYMBOL_PATTERNS = (
    re.compile(r"(?:async\s+def|def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    re.compile(r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    re.compile(r"(?:export\s+)?class\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    re.compile(r"(?:pub\s+)?(?:fn|struct|enum|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
)

# ---------------------------------------------------------------------------
# Ground truth query set (real TunaCode files)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkQuery:
    label: str
    query: str
    expected_files: tuple[str, ...]
    expected_symbols: tuple[str, ...]


QUERIES: tuple[BenchmarkQuery, ...] = (
    BenchmarkQuery(
        label="decorators + tinyagent",
        query="tool decorators and tinyagent adapter registration",
        expected_files=("src/tunacode/tools/decorators.py",),
        expected_symbols=("base_tool", "to_tinyagent_tool"),
    ),
    BenchmarkQuery(
        label="discover clustering",
        query="discover relevance scoring and concept clustering",
        expected_files=("src/tunacode/tools/discover.py",),
        expected_symbols=("_cluster_prospects", "_evaluate_prospect"),
    ),
    BenchmarkQuery(
        label="ignore cache + mtime",
        query="ignore manager cache invalidation using gitignore mtime",
        expected_files=(
            "src/tunacode/tools/cache_accessors/ignore_manager_cache.py",
            "src/tunacode/tools/ignore_manager.py",
        ),
        expected_symbols=("get_ignore_manager", "get_gitignore_mtime_ns"),
    ),
    BenchmarkQuery(
        label="ripgrep execution",
        query="ripgrep binary resolution and async subprocess search",
        expected_files=("src/tunacode/tools/utils/ripgrep.py",),
        expected_symbols=("get_ripgrep_binary_path", "RipgrepExecutor"),
    ),
    BenchmarkQuery(
        label="agent tool registration",
        query="where agent config registers tools for tinyagent",
        expected_files=("src/tunacode/core/agents/agent_components/agent_config.py",),
        expected_symbols=("_build_tools", "get_or_create_agent"),
    ),
    BenchmarkQuery(
        label="compaction pipeline",
        query="compaction controller with context summarizer flow",
        expected_files=(
            "src/tunacode/core/compaction/controller.py",
            "src/tunacode/core/compaction/summarizer.py",
        ),
        expected_symbols=("CompactionController", "ContextSummarizer"),
    ),
    BenchmarkQuery(
        label="web fetch safety",
        query="web fetch url validation and html conversion",
        expected_files=("src/tunacode/tools/web_fetch.py",),
        expected_symbols=("_validate_url", "_convert_html_to_text"),
    ),
    BenchmarkQuery(
        label="lsp diagnostics",
        query="lsp client diagnostics and settings checks",
        expected_files=(
            "src/tunacode/tools/lsp/client.py",
            "src/tunacode/tools/lsp/diagnostics.py",
        ),
        expected_symbols=("LSPClient", "maybe_prepend_lsp_diagnostics"),
    ),
    BenchmarkQuery(
        label="cache manager strategy",
        query="cache manager entries and mtime strategy logic",
        expected_files=(
            "src/tunacode/infrastructure/cache/manager.py",
            "src/tunacode/infrastructure/cache/strategies.py",
        ),
        expected_symbols=("CacheManager", "MtimeStrategy"),
    ),
    BenchmarkQuery(
        label="model picker filtering",
        query="model picker option filtering and highlight index",
        expected_files=("src/tunacode/ui/screens/model_picker.py",),
        expected_symbols=("_filter_visible_items", "_choose_highlight_index"),
    ),
    BenchmarkQuery(
        label="tool renderer registry",
        query="tool renderer registration and renderer lookup",
        expected_files=("src/tunacode/ui/renderers/tools/base.py",),
        expected_symbols=("tool_renderer", "get_renderer"),
    ),
    BenchmarkQuery(
        label="session state objects",
        query="session state and state manager objects",
        expected_files=("src/tunacode/core/session/state.py",),
        expected_symbols=("SessionState", "StateManager"),
    ),
)


# ---------------------------------------------------------------------------
# Bench result models
# ---------------------------------------------------------------------------


@dataclass
class StrategyRun:
    strategy: str
    latency_ms: float
    tool_calls: int
    output_chars: int
    files: list[str]
    symbols: list[str]
    clusters: int


@dataclass
class MeasuredRun:
    mode: str
    query_label: str
    strategy: str
    latency_ms: float
    tool_calls: float
    output_tokens: float
    file_recall: float
    symbol_recall: float
    first_hit_rank: float
    actionable: float
    clusters: float


# ---------------------------------------------------------------------------
# Legacy chain tools (real tool-call overhead, no synthetic repository)
# ---------------------------------------------------------------------------


def _normalize_relative_path(path_text: str, root: Path) -> str:
    path_text = path_text.strip()
    if not path_text:
        return ""

    candidate = Path(path_text)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return resolved.as_posix()

    return rel.as_posix()


def _is_hidden_path(path: Path) -> bool:
    return any(part.startswith(HIDDEN_PREFIX) for part in path.parts)


def _collect_list_dir_files(root: Path, max_files: int) -> list[str]:
    ignore_manager = get_ignore_manager(root)
    collected: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)

        filtered_dirs: list[str] = []
        for dirname in sorted(dirnames):
            child_dir = dir_path / dirname
            if _is_hidden_path(child_dir.relative_to(root)):
                continue
            if ignore_manager.should_ignore_dir(child_dir):
                continue
            filtered_dirs.append(dirname)
        dirnames[:] = filtered_dirs

        for filename in sorted(filenames):
            child_file = dir_path / filename
            rel_path = child_file.relative_to(root)
            if _is_hidden_path(rel_path):
                continue
            if ignore_manager.should_ignore(child_file):
                continue
            collected.append(rel_path.as_posix())
            if len(collected) >= max_files:
                return collected

    return collected


@base_tool
async def legacy_list_dir(directory: str = ".", max_files: int = LEGACY_LIST_MAX_FILES) -> str:
    root = Path(directory).resolve()
    files = await asyncio.to_thread(_collect_list_dir_files, root, max_files)
    return "\n".join(files)


def _collect_glob_candidates(root: Path, query: str, max_files: int) -> list[str]:
    ignore_manager = get_ignore_manager(root)
    terms = _extract_search_terms(query)["filename"]
    lowered_terms = tuple(term.lower() for term in terms)

    if not lowered_terms:
        return []

    candidates: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        if ignore_manager.should_ignore(path):
            continue

        rel = path.relative_to(root).as_posix()
        rel_lower = rel.lower()
        if not any(term in rel_lower for term in lowered_terms):
            continue

        candidates.append(rel)
        if len(candidates) >= max_files:
            break

    return candidates


@base_tool
async def legacy_glob(
    query: str,
    directory: str = ".",
    max_files: int = LEGACY_GLOB_MAX_FILES,
) -> str:
    root = Path(directory).resolve()
    candidates = await asyncio.to_thread(_collect_glob_candidates, root, query, max_files)
    return "\n".join(candidates)


def _build_legacy_grep_pattern(query: str) -> str:
    terms = _extract_search_terms(query)["content"]
    compact_terms: list[str] = []

    for term in terms:
        normalized_term = term.strip().lower()
        if len(normalized_term) < 3:
            continue
        if normalized_term in compact_terms:
            continue
        compact_terms.append(normalized_term)
        if len(compact_terms) >= LEGACY_GREP_TERM_LIMIT:
            break

    if not compact_terms:
        return ""

    escaped = [re.escape(term) for term in compact_terms]
    return "|".join(escaped)


def _parse_path_lines(text: str, root: Path) -> list[str]:
    ranked_paths: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        head = line.split(":", 1)[0]
        normalized = _normalize_relative_path(head, root)
        if not normalized:
            continue
        if normalized in seen:
            continue

        candidate_path = root / normalized
        if not candidate_path.exists():
            continue

        seen.add(normalized)
        ranked_paths.append(normalized)

    return ranked_paths


@base_tool
async def legacy_grep(
    query: str,
    directory: str = ".",
    candidates: str = "",
    max_matches: int = LEGACY_GREP_MAX_MATCHES,
) -> str:
    root = Path(directory).resolve()
    candidate_set = set(_parse_path_lines(candidates, root))

    pattern = _build_legacy_grep_pattern(query)
    if not pattern:
        return ""

    executor = RipgrepExecutor()
    lines = await executor.search(
        pattern=pattern,
        path=str(root),
        max_matches=max_matches,
        case_insensitive=True,
    )

    filtered: list[str] = []
    for line in lines:
        file_head = line.split(":", 1)[0]
        normalized = _normalize_relative_path(file_head, root)
        if not normalized:
            continue

        if candidate_set and normalized not in candidate_set:
            continue

        filtered.append(line)
        if len(filtered) >= max_matches:
            break

    return "\n".join(filtered)


# ---------------------------------------------------------------------------
# Parsing and metrics
# ---------------------------------------------------------------------------


def _estimate_tokens(output_chars: int) -> int:
    if output_chars <= 0:
        return 0
    return math.ceil(output_chars / TOKEN_CHARS_PER_TOKEN)


def _extract_symbols(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for pattern in SYMBOL_PATTERNS:
        for symbol in pattern.findall(text):
            if symbol in seen:
                continue
            seen.add(symbol)
            found.append(symbol)

    return found


def _parse_discover_files(output_text: str, root: Path) -> list[str]:
    matches = DISCOVER_FILE_PATTERN.findall(output_text)
    files: list[str] = []
    seen: set[str] = set()

    for raw_path in matches:
        normalized = _normalize_relative_path(raw_path, root)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        files.append(normalized)

    return files


def _parse_discover_symbols(output_text: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()

    for line in output_text.splitlines():
        match = DISCOVER_DEFINES_PATTERN.search(line)
        if match is None:
            continue

        items = [item.strip() for item in match.group(1).split(",")]
        for item in items:
            if not item:
                continue
            if item in seen:
                continue
            seen.add(item)
            symbols.append(item)

    return symbols


def _count_discover_clusters(output_text: str) -> int:
    return sum(1 for line in output_text.splitlines() if line.startswith("## "))


def _safe_recall(hit_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 1.0
    return hit_count / total_count


def _first_hit_rank(files: list[str], expected_files: set[str]) -> int:
    for index, path in enumerate(files, start=1):
        if path in expected_files:
            return index
    return 0


def _score_run(mode: str, query: BenchmarkQuery, run: StrategyRun) -> MeasuredRun:
    expected_files_set = set(query.expected_files)
    expected_symbols_set = {symbol.lower() for symbol in query.expected_symbols}

    found_files_set = set(run.files)
    found_symbols_set = {symbol.lower() for symbol in run.symbols}

    file_hits = len(found_files_set & expected_files_set)
    symbol_hits = len(found_symbols_set & expected_symbols_set)

    file_recall = _safe_recall(file_hits, len(expected_files_set))
    symbol_recall = _safe_recall(symbol_hits, len(expected_symbols_set))

    rank = _first_hit_rank(run.files, expected_files_set)

    rank_is_actionable = rank > 0 and rank <= ACTIONABLE_TOP_FILE_RANK
    symbol_is_actionable = symbol_recall >= ACTIONABLE_SYMBOL_RECALL_THRESHOLD
    actionable = rank_is_actionable or symbol_is_actionable

    return MeasuredRun(
        mode=mode,
        query_label=query.label,
        strategy=run.strategy,
        latency_ms=run.latency_ms,
        tool_calls=float(run.tool_calls),
        output_tokens=float(_estimate_tokens(run.output_chars)),
        file_recall=file_recall,
        symbol_recall=symbol_recall,
        first_hit_rank=float(rank),
        actionable=1.0 if actionable else 0.0,
        clusters=float(run.clusters),
    )


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    scaled_index = (len(ordered) - 1) * percentile
    lower_index = math.floor(scaled_index)
    upper_index = math.ceil(scaled_index)

    if lower_index == upper_index:
        return ordered[lower_index]

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    fraction = scaled_index - lower_index

    return lower_value + (upper_value - lower_value) * fraction


# ---------------------------------------------------------------------------
# Tool invocation
# ---------------------------------------------------------------------------


def _drop_updates(_: Any) -> None:
    return


def _tool_result_to_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if not isinstance(content, list):
        return str(result)

    chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            chunks.append(str(item))
            continue

        text = item.get("text")
        if isinstance(text, str):
            chunks.append(text)

    return "\n".join(chunks)


async def _invoke_tool(tool: AgentTool, args: dict[str, Any]) -> str:
    result = await tool.execute(BENCH_TOOL_CALL_ID, args, None, _drop_updates)
    return _tool_result_to_text(result)


# ---------------------------------------------------------------------------
# Benchmark strategy runners
# ---------------------------------------------------------------------------


async def _run_discover(query: BenchmarkQuery, root: Path) -> StrategyRun:
    discover_tool = to_tinyagent_tool(discover)

    start = time.perf_counter()
    output_text = await _invoke_tool(discover_tool, {"query": query.query, "directory": str(root)})
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    files = _parse_discover_files(output_text, root)
    symbols = _parse_discover_symbols(output_text)
    clusters = _count_discover_clusters(output_text)

    return StrategyRun(
        strategy="discover",
        latency_ms=elapsed_ms,
        tool_calls=1,
        output_chars=len(output_text),
        files=files,
        symbols=symbols,
        clusters=clusters,
    )


async def _run_legacy_chain(query: BenchmarkQuery, root: Path) -> StrategyRun:
    list_tool = to_tinyagent_tool(legacy_list_dir, name="list_dir")
    glob_tool = to_tinyagent_tool(legacy_glob, name="glob")
    grep_tool = to_tinyagent_tool(legacy_grep, name="grep")
    read_tool = to_tinyagent_tool(read_file, name="read_file")

    start = time.perf_counter()

    list_output = await _invoke_tool(
        list_tool,
        {"directory": str(root), "max_files": LEGACY_LIST_MAX_FILES},
    )

    glob_output = await _invoke_tool(
        glob_tool,
        {
            "query": query.query,
            "directory": str(root),
            "max_files": LEGACY_GLOB_MAX_FILES,
        },
    )

    grep_output = await _invoke_tool(
        grep_tool,
        {
            "query": query.query,
            "directory": str(root),
            "candidates": glob_output,
            "max_matches": LEGACY_GREP_MAX_MATCHES,
        },
    )

    ranked_files = _parse_path_lines(grep_output, root)
    if not ranked_files:
        ranked_files = _parse_path_lines(glob_output, root)

    read_targets = ranked_files[:LEGACY_READ_FILE_LIMIT]

    read_outputs: list[str] = []
    for rel_path in read_targets:
        read_output = await _invoke_tool(
            read_tool,
            {
                "filepath": str((root / rel_path).resolve()),
                "limit": LEGACY_READ_LINE_LIMIT,
            },
        )
        read_outputs.append(read_output)

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    output_segments = [list_output, glob_output, grep_output, *read_outputs]
    output_chars = sum(len(segment) for segment in output_segments)

    symbols = _extract_symbols("\n".join([grep_output, *read_outputs]))

    return StrategyRun(
        strategy="legacy",
        latency_ms=elapsed_ms,
        tool_calls=3 + len(read_outputs),
        output_chars=output_chars,
        files=ranked_files,
        symbols=symbols,
        clusters=0,
    )


def _clear_benchmark_caches() -> None:
    clear_ignore_manager_cache()
    clear_ripgrep_cache()
    clear_xml_prompts_cache()


async def _prime_warm_caches(root: Path) -> None:
    seed_query = QUERIES[0]
    _clear_benchmark_caches()
    await _run_discover(seed_query, root)
    await _run_legacy_chain(seed_query, root)


async def _run_mode(mode: str, root: Path) -> list[MeasuredRun]:
    if mode not in {MODE_COLD, MODE_WARM}:
        raise ValueError(f"Unknown benchmark mode: {mode}")

    if mode == MODE_WARM:
        await _prime_warm_caches(root)

    run_count = COLD_RUNS_PER_QUERY if mode == MODE_COLD else WARM_RUNS_PER_QUERY
    measured: list[MeasuredRun] = []

    for query in QUERIES:
        for _ in range(run_count):
            if mode == MODE_COLD:
                _clear_benchmark_caches()
            discover_run = await _run_discover(query, root)
            measured.append(_score_run(mode, query, discover_run))

            if mode == MODE_COLD:
                _clear_benchmark_caches()
            legacy_run = await _run_legacy_chain(query, root)
            measured.append(_score_run(mode, query, legacy_run))

    return measured


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _rows_for(measured: list[MeasuredRun], mode: str, strategy: str) -> list[MeasuredRun]:
    return [row for row in measured if row.mode == mode and row.strategy == strategy]


def _rows_for_query(
    measured: list[MeasuredRun],
    mode: str,
    strategy: str,
    query_label: str,
) -> list[MeasuredRun]:
    return [
        row
        for row in measured
        if row.mode == mode and row.strategy == strategy and row.query_label == query_label
    ]


def _print_mode_table(measured: list[MeasuredRun], mode: str) -> None:
    col_query = 26
    col_num = 8

    header = (
        f"{'Query':<{col_query}} "
        f"{'D-ms':>{col_num}} "
        f"{'L-ms':>{col_num}} "
        f"{'D-tok':>{col_num}} "
        f"{'L-tok':>{col_num}} "
        f"{'D-call':>{col_num}} "
        f"{'L-call':>{col_num}} "
        f"{'D-frec':>{col_num}} "
        f"{'L-frec':>{col_num}} "
        f"{'D-srec':>{col_num}} "
        f"{'L-srec':>{col_num}} "
        f"{'D-act':>{col_num}} "
        f"{'L-act':>{col_num}}"
    )

    print(f"\n--- {mode.upper()} ---")
    print(header)
    print("-" * len(header))

    for query in QUERIES:
        discover_rows = _rows_for_query(measured, mode, "discover", query.label)
        legacy_rows = _rows_for_query(measured, mode, "legacy", query.label)

        d_ms = _avg([row.latency_ms for row in discover_rows])
        l_ms = _avg([row.latency_ms for row in legacy_rows])

        d_tok = _avg([row.output_tokens for row in discover_rows])
        l_tok = _avg([row.output_tokens for row in legacy_rows])

        d_calls = _avg([row.tool_calls for row in discover_rows])
        l_calls = _avg([row.tool_calls for row in legacy_rows])

        d_file_recall = _avg([row.file_recall for row in discover_rows])
        l_file_recall = _avg([row.file_recall for row in legacy_rows])

        d_symbol_recall = _avg([row.symbol_recall for row in discover_rows])
        l_symbol_recall = _avg([row.symbol_recall for row in legacy_rows])

        d_actionable = _avg([row.actionable for row in discover_rows])
        l_actionable = _avg([row.actionable for row in legacy_rows])

        print(
            f"{query.label:<{col_query}} "
            f"{d_ms:>{col_num}.1f} "
            f"{l_ms:>{col_num}.1f} "
            f"{d_tok:>{col_num}.0f} "
            f"{l_tok:>{col_num}.0f} "
            f"{d_calls:>{col_num}.1f} "
            f"{l_calls:>{col_num}.1f} "
            f"{d_file_recall:>{col_num}.2f} "
            f"{l_file_recall:>{col_num}.2f} "
            f"{d_symbol_recall:>{col_num}.2f} "
            f"{l_symbol_recall:>{col_num}.2f} "
            f"{d_actionable:>{col_num}.2f} "
            f"{l_actionable:>{col_num}.2f}"
        )

    discover_rows = _rows_for(measured, mode, "discover")
    legacy_rows = _rows_for(measured, mode, "legacy")

    print("-" * len(header))
    print(
        f"{'AVG':<{col_query}} "
        f"{_avg([row.latency_ms for row in discover_rows]):>{col_num}.1f} "
        f"{_avg([row.latency_ms for row in legacy_rows]):>{col_num}.1f} "
        f"{_avg([row.output_tokens for row in discover_rows]):>{col_num}.0f} "
        f"{_avg([row.output_tokens for row in legacy_rows]):>{col_num}.0f} "
        f"{_avg([row.tool_calls for row in discover_rows]):>{col_num}.1f} "
        f"{_avg([row.tool_calls for row in legacy_rows]):>{col_num}.1f} "
        f"{_avg([row.file_recall for row in discover_rows]):>{col_num}.2f} "
        f"{_avg([row.file_recall for row in legacy_rows]):>{col_num}.2f} "
        f"{_avg([row.symbol_recall for row in discover_rows]):>{col_num}.2f} "
        f"{_avg([row.symbol_recall for row in legacy_rows]):>{col_num}.2f} "
        f"{_avg([row.actionable for row in discover_rows]):>{col_num}.2f} "
        f"{_avg([row.actionable for row in legacy_rows]):>{col_num}.2f}"
    )


def _print_strategy_distribution(measured: list[MeasuredRun], mode: str) -> None:
    discover_rows = _rows_for(measured, mode, "discover")
    legacy_rows = _rows_for(measured, mode, "legacy")

    discover_latencies = [row.latency_ms for row in discover_rows]
    legacy_latencies = [row.latency_ms for row in legacy_rows]

    discover_calls = _avg([row.tool_calls for row in discover_rows])
    legacy_calls = _avg([row.tool_calls for row in legacy_rows])

    discover_tokens = _avg([row.output_tokens for row in discover_rows])
    legacy_tokens = _avg([row.output_tokens for row in legacy_rows])

    discover_actionable = _avg([row.actionable for row in discover_rows])
    legacy_actionable = _avg([row.actionable for row in legacy_rows])

    discover_file_recall = _avg([row.file_recall for row in discover_rows])
    legacy_file_recall = _avg([row.file_recall for row in legacy_rows])

    discover_symbol_recall = _avg([row.symbol_recall for row in discover_rows])
    legacy_symbol_recall = _avg([row.symbol_recall for row in legacy_rows])

    call_ratio = legacy_calls / discover_calls if discover_calls > 0 else 0.0
    token_ratio = legacy_tokens / discover_tokens if discover_tokens > 0 else 0.0
    latency_ratio = legacy_latencies and discover_latencies
    if latency_ratio:
        avg_legacy_latency = _avg(legacy_latencies)
        avg_discover_latency = _avg(discover_latencies)
        latency_ratio_value = (
            avg_legacy_latency / avg_discover_latency if avg_discover_latency > 0 else 0.0
        )
    else:
        latency_ratio_value = 0.0

    print(f"\n[{mode}] Distribution")
    print(
        "  discover "
        f"p50={_percentile(discover_latencies, PERCENTILE_P50):.1f}ms "
        f"p95={_percentile(discover_latencies, PERCENTILE_P95):.1f}ms "
        f"calls={discover_calls:.1f} "
        f"tokens={discover_tokens:.0f} "
        f"file_recall={discover_file_recall:.2f} "
        f"symbol_recall={discover_symbol_recall:.2f} "
        f"actionable={discover_actionable:.2f}"
    )
    print(
        "  legacy   "
        f"p50={_percentile(legacy_latencies, PERCENTILE_P50):.1f}ms "
        f"p95={_percentile(legacy_latencies, PERCENTILE_P95):.1f}ms "
        f"calls={legacy_calls:.1f} "
        f"tokens={legacy_tokens:.0f} "
        f"file_recall={legacy_file_recall:.2f} "
        f"symbol_recall={legacy_symbol_recall:.2f} "
        f"actionable={legacy_actionable:.2f}"
    )
    print(
        "  ratios   "
        f"calls={call_ratio:.2f}x "
        f"tokens={token_ratio:.2f}x "
        f"latency={latency_ratio_value:.2f}x"
    )


def _validate_query_targets(root: Path) -> None:
    for query in QUERIES:
        for rel_path in query.expected_files:
            target = root / rel_path
            if target.exists():
                continue
            raise FileNotFoundError(f"Benchmark target file missing: {target}")


async def _run_all_modes(root: Path) -> list[MeasuredRun]:
    cold_rows = await _run_mode(MODE_COLD, root)
    warm_rows = await _run_mode(MODE_WARM, root)
    return [*cold_rows, *warm_rows]


def main() -> None:
    _validate_query_targets(REPO_ROOT)

    print("=" * 92)
    print("Discover Benchmark (Real TunaCode Repo)")
    print("=" * 92)
    print(f"Repo root: {REPO_ROOT}")
    print(f"Queries: {len(QUERIES)}")
    print(f"Modes: cold({COLD_RUNS_PER_QUERY} run/query), warm({WARM_RUNS_PER_QUERY} runs/query)")
    print("Token estimate: ceil(chars / 4)")

    measured = asyncio.run(_run_all_modes(REPO_ROOT))

    _print_mode_table(measured, MODE_COLD)
    _print_strategy_distribution(measured, MODE_COLD)

    _print_mode_table(measured, MODE_WARM)
    _print_strategy_distribution(measured, MODE_WARM)


if __name__ == "__main__":
    main()
