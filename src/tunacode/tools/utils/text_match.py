"""
Module: tunacode.tools.edit_replacers

Fuzzy string replacement strategies for the update_file tool.
Inspired by:
- https://github.com/cline/cline/blob/main/evals/diff-edits/diff-apply/diff-06-23-25.ts
- https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/utils/editCorrector.ts
- https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/edit.ts

Each replacer is a generator that yields potential matches found in content.
Replacers are tried in order from strict to fuzzy until one succeeds.
"""

from collections.abc import Callable, Generator
from typing import NoReturn

try:
    from Levenshtein import distance as _levenshtein_c

    _USE_C_LEVENSHTEIN = True
except ImportError:
    _USE_C_LEVENSHTEIN = False

# Type alias for replacer functions
Replacer = Callable[[str, str], Generator[str, None, None]]

# Similarity thresholds for block anchor fallback matching
SINGLE_CANDIDATE_SIMILARITY_THRESHOLD = 0.0
MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD = 0.3

ANCHOR_LINE_COUNT = 2
MIN_ANCHOR_LINES = ANCHOR_LINE_COUNT + 1
ANCHOR_EDGE_OFFSET = 1
MIN_ANCHOR_DISTANCE = ANCHOR_LINE_COUNT
FULL_SIMILARITY = 1.0
NO_SIMILARITY = 0.0
UNSET_SIMILARITY = -1.0
LINE_ENDING_CHARS = "\r\n"


def levenshtein(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings."""
    if _USE_C_LEVENSHTEIN:
        return _levenshtein_c(a, b)

    if not a or not b:
        return max(len(a), len(b))

    matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        matrix[i][0] = i
    for j in range(len(b) + 1):
        matrix[0][j] = j

    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,  # deletion
                matrix[i][j - 1] + 1,  # insertion
                matrix[i - 1][j - 1] + cost,  # substitution
            )
    return matrix[len(a)][len(b)]


def simple_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Exact match replacer - yields find string if present in content.

    This is the strictest matcher and preserves backwards compatibility.
    """
    if find in content:
        yield find


def line_trimmed_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match lines ignoring leading/trailing whitespace per line.

    Compares trimmed versions of each line but yields the original
    content with its actual whitespace preserved.
    """
    # Use splitlines(keepends=True) to handle both \n and \r\n correctly
    original_lines = content.splitlines(keepends=True)
    search_lines = find.split("\n")

    # Remove trailing empty line if present (common from copy-paste)
    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    if not search_lines:
        return

    for i in range(len(original_lines) - len(search_lines) + 1):
        matches = True

        for j in range(len(search_lines)):
            original_trimmed = original_lines[i + j].strip()
            search_trimmed = search_lines[j].strip()

            if original_trimmed != search_trimmed:
                matches = False
                break

        if matches:
            # Join the matched lines and strip trailing line ending
            matched_block = "".join(original_lines[i : i + len(search_lines)])
            yield matched_block.rstrip(LINE_ENDING_CHARS)


def _remove_indentation(text: str) -> str:
    """Remove common leading indentation from all lines."""
    lines = text.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]

    if not non_empty_lines:
        return text

    min_indent = _min_indentation(non_empty_lines)

    if min_indent == 0:
        return text

    return "\n".join(line[min_indent:] if line.strip() else line for line in lines)


def _min_indentation(non_empty_lines: list[str]) -> int:
    """Return the minimum leading whitespace count across non-empty lines."""
    result = float("inf")
    for line in non_empty_lines:
        stripped = line.lstrip()
        if stripped:
            result = min(result, len(line) - len(stripped))
    return 0 if result == float("inf") else int(result)


def indentation_flexible_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match blocks after normalizing indentation.

    Strips the minimum common indentation from both content blocks
    and find string, then compares. Useful when the LLM gets the
    indentation level wrong but the code structure is correct.
    """
    content_lines = content.split("\n")
    find_lines = find.split("\n")

    # Remove trailing empty line if present (MUST happen before normalization)
    if find_lines and find_lines[-1] == "":
        find_lines.pop()

    if not find_lines:
        return

    # Normalize find AFTER trimming trailing empty line
    normalized_find = _remove_indentation("\n".join(find_lines))

    # Pre-compute first line stripped for fail-fast check
    first_find_stripped = find_lines[0].strip()

    for i in range(len(content_lines) - len(find_lines) + 1):
        # Fail-fast: skip if first line doesn't match (ignoring indentation)
        if content_lines[i].strip() != first_find_stripped:
            continue

        block = "\n".join(content_lines[i : i + len(find_lines)])
        if _remove_indentation(block) == normalized_find:
            yield block


def _trim_trailing_empty_line(lines: list[str]) -> list[str]:
    """Remove trailing empty line from a list of lines."""
    if lines and lines[-1] == "":
        return lines[:-1]
    return lines


def _prepare_search_lines(find: str) -> list[str] | None:
    """Split and normalize search lines for anchor matching."""
    search_lines = _trim_trailing_empty_line(find.split("\n"))
    if len(search_lines) < MIN_ANCHOR_LINES:
        return None
    return search_lines


def _find_anchor_candidates(
    original_lines: list[str],
    first_line_search: str,
    last_line_search: str,
) -> list[tuple[int, int]]:
    """Return candidate anchor start/end indices in original_lines."""
    first_indices = [
        i for i, line in enumerate(original_lines) if line.strip() == first_line_search
    ]
    last_indices = [j for j, line in enumerate(original_lines) if line.strip() == last_line_search]

    if not first_indices or not last_indices:
        return []

    candidates: list[tuple[int, int]] = []
    for start_line in first_indices:
        for end_line in last_indices:
            if end_line - start_line < MIN_ANCHOR_DISTANCE:
                continue
            candidates.append((start_line, end_line))
            break

    return candidates


def _yield_block(original_lines: list[str], start: int, end: int) -> str:
    """Join lines from start to end (inclusive) and strip trailing line ending."""
    return "".join(original_lines[start : end + 1]).rstrip(LINE_ENDING_CHARS)


def _lines_to_check(search_block_size: int, actual_block_size: int) -> int:
    middle_search_lines = search_block_size - ANCHOR_LINE_COUNT
    middle_actual_lines = actual_block_size - ANCHOR_LINE_COUNT
    return min(middle_search_lines, middle_actual_lines)


def _line_similarity(original_line: str, search_line: str) -> float | None:
    max_len = max(len(original_line), len(search_line))
    if max_len == 0:
        return None
    distance = levenshtein(original_line, search_line)
    return FULL_SIMILARITY - distance / max_len


def _candidate_similarity(
    original_lines: list[str],
    search_lines: list[str],
    start_line: int,
    end_line: int,
    early_exit_threshold: float | None,
) -> float:
    actual_block_size = end_line - start_line + 1
    search_block_size = len(search_lines)
    lines_to_check = _lines_to_check(search_block_size, actual_block_size)

    if lines_to_check <= 0:
        return FULL_SIMILARITY

    similarity = NO_SIMILARITY
    end_index = min(
        search_block_size - ANCHOR_EDGE_OFFSET,
        actual_block_size - ANCHOR_EDGE_OFFSET,
    )
    for line_index in range(ANCHOR_EDGE_OFFSET, end_index):
        original_line = original_lines[start_line + line_index].strip()
        search_line = search_lines[line_index].strip()
        line_similarity = _line_similarity(original_line, search_line)
        if line_similarity is None:
            continue
        if early_exit_threshold is not None:
            similarity += line_similarity / lines_to_check
            if similarity >= early_exit_threshold:
                break
        else:
            similarity += line_similarity

    if early_exit_threshold is not None:
        return similarity

    return similarity / lines_to_check


def _select_best_match(
    original_lines: list[str],
    search_lines: list[str],
    candidates: list[tuple[int, int]],
) -> tuple[int, int] | None:
    best_match: tuple[int, int] | None = None
    max_similarity = UNSET_SIMILARITY

    for start_line, end_line in candidates:
        similarity = _candidate_similarity(
            original_lines,
            search_lines,
            start_line,
            end_line,
            early_exit_threshold=None,
        )
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = (start_line, end_line)

    if max_similarity < MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD:
        return None

    return best_match


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match using first/last lines as anchors, fuzzy-match middle.

    This is the fuzziest matcher. It:
    1. Finds blocks where first and last lines match exactly (trimmed)
    2. Uses Levenshtein distance to score middle line similarity
    3. Returns best match if similarity exceeds threshold
    """
    # Use splitlines(keepends=True) to handle both \n and \r\n correctly
    original_lines = content.splitlines(keepends=True)
    search_lines = _prepare_search_lines(find)

    if search_lines is None:
        return

    first_line_search = search_lines[0].strip()
    last_line_search = search_lines[-1].strip()
    candidates = _find_anchor_candidates(original_lines, first_line_search, last_line_search)

    if not candidates:
        return

    if len(candidates) == 1:
        start_line, end_line = candidates[0]
        similarity = _candidate_similarity(
            original_lines,
            search_lines,
            start_line,
            end_line,
            early_exit_threshold=SINGLE_CANDIDATE_SIMILARITY_THRESHOLD,
        )
        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            yield _yield_block(original_lines, start_line, end_line)
        return

    best_match = _select_best_match(original_lines, search_lines, candidates)
    if best_match is None:
        return

    start_line, end_line = best_match
    yield _yield_block(original_lines, start_line, end_line)


# Ordered list of replacers from strict to fuzzy
REPLACERS: list[Replacer] = [
    simple_replacer,
    line_trimmed_replacer,
    indentation_flexible_replacer,
    block_anchor_replacer,
]


def _try_replace_all(content: str, search: str, new_string: str, is_exact: bool) -> str | None:
    """Attempt replace-all for exact matches only. Returns modified content or None."""
    if not is_exact:
        return None
    return content.replace(search, new_string)


def _try_replace_unique(content: str, search: str, new_string: str) -> str | None:
    """Replace search in content only if it appears exactly once. Returns None on duplicate."""
    index = content.find(search)
    if index == -1:
        return None
    if content.rfind(search) != index:
        return None
    return content[:index] + new_string + content[index + len(search) :]


def _raise_replace_error(found_fuzzy_match_for_replace_all: bool, found_multiple: bool) -> NoReturn:
    """Raise the appropriate ValueError for a failed replace."""
    if found_fuzzy_match_for_replace_all:
        raise ValueError(
            "replace_all=True only allowed with exact matches. "
            "Fuzzy matching found a match but replace_all is risky for non-exact matches."
        )

    if found_multiple:
        raise ValueError(
            "Found multiple matches for old_string. "
            "Provide more surrounding lines in old_string to identify the correct match."
        )

    raise ValueError("old_string not found in content (tried all fuzzy matching strategies)")


def replace(content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace old_string with new_string using fuzzy matching.

    Tries each replacer in order until one succeeds. Replacers are ordered
    from strict (exact match) to fuzzy (anchor-based with Levenshtein).

    Args:
        content: The file content to modify
        old_string: The text to find and replace
        new_string: The replacement text
        replace_all: If True, replace all occurrences; if False, require unique match

    Returns:
        Modified content with replacement applied

    Raises:
        ValueError: If old_string equals new_string
        ValueError: If no match found after trying all strategies
        ValueError: If multiple matches found and replace_all is False
    """
    if old_string == "":
        raise ValueError("old_string cannot be empty; handle file overwrite separately")

    if old_string == new_string:
        raise ValueError("old_string and new_string must be different")

    found_multiple = False
    found_fuzzy_match_for_replace_all = False

    for replacer_idx, replacer in enumerate(REPLACERS):
        is_exact_match = replacer_idx == 0  # simple_replacer is exact

        for search in replacer(content, old_string):
            if content.find(search) == -1:
                continue

            if replace_all:
                result = _try_replace_all(content, search, new_string, is_exact_match)
                if result is not None:
                    return result
                found_fuzzy_match_for_replace_all = True
                continue

            result = _try_replace_unique(content, search, new_string)
            if result is not None:
                return result
            found_multiple = True

    _raise_replace_error(found_fuzzy_match_for_replace_all, found_multiple)
