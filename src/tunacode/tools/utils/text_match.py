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
            yield matched_block.rstrip("\r\n")


def indentation_flexible_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match blocks after normalizing indentation.

    Strips the minimum common indentation from both content blocks
    and find string, then compares. Useful when the LLM gets the
    indentation level wrong but the code structure is correct.
    """

    def remove_indentation(text: str) -> str:
        """Remove common leading indentation from all lines."""
        lines = text.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]

        if not non_empty_lines:
            return text

        # Find minimum indentation
        min_indent = float("inf")
        for line in non_empty_lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                min_indent = min(min_indent, indent)

        if min_indent == float("inf") or min_indent == 0:
            return text

        # Remove the common indentation
        result_lines = []
        for line in lines:
            if line.strip():
                result_lines.append(line[int(min_indent) :])
            else:
                result_lines.append(line)

        return "\n".join(result_lines)

    content_lines = content.split("\n")
    find_lines = find.split("\n")

    # Remove trailing empty line if present (MUST happen before normalization)
    if find_lines and find_lines[-1] == "":
        find_lines.pop()

    if not find_lines:
        return

    # Normalize find AFTER trimming trailing empty line
    normalized_find = remove_indentation("\n".join(find_lines))

    # Pre-compute first line stripped for fail-fast check
    first_find_stripped = find_lines[0].strip()

    for i in range(len(content_lines) - len(find_lines) + 1):
        # Fail-fast: skip if first line doesn't match (ignoring indentation)
        if content_lines[i].strip() != first_find_stripped:
            continue

        block = "\n".join(content_lines[i : i + len(find_lines)])
        if remove_indentation(block) == normalized_find:
            yield block


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match using first/last lines as anchors, fuzzy-match middle.

    This is the fuzziest matcher. It:
    1. Finds blocks where first and last lines match exactly (trimmed)
    2. Uses Levenshtein distance to score middle line similarity
    3. Returns best match if similarity exceeds threshold
    """
    # Use splitlines(keepends=True) to handle both \n and \r\n correctly
    original_lines = content.splitlines(keepends=True)
    search_lines = find.split("\n")

    # Need at least 3 lines for anchor matching to make sense
    if len(search_lines) < 3:
        return

    # Remove trailing empty line if present
    if search_lines[-1] == "":
        search_lines.pop()

    if len(search_lines) < 3:
        return

    first_line_search = search_lines[0].strip()
    last_line_search = search_lines[-1].strip()
    search_block_size = len(search_lines)

    # Build indices in O(n) instead of O(n^2) nested loop
    first_indices = [
        i for i, line in enumerate(original_lines) if line.strip() == first_line_search
    ]
    last_indices = [j for j, line in enumerate(original_lines) if line.strip() == last_line_search]

    if not first_indices or not last_indices:
        return

    # Find valid pairs in O(k^2) where k << n typically
    candidates: list[tuple[int, int]] = []
    for i in first_indices:
        for j in last_indices:
            if j > i + 1:  # Need at least one line between anchors
                candidates.append((i, j))
                break  # Only first matching last anchor after this first

    if not candidates:
        return

    def yield_block(start: int, end: int) -> str:
        """Join lines from start to end (inclusive) and strip trailing line ending."""
        return "".join(original_lines[start : end + 1]).rstrip("\r\n")

    # Handle single candidate (use relaxed threshold)
    if len(candidates) == 1:
        start_line, end_line = candidates[0]
        actual_block_size = end_line - start_line + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[start_line + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(original_line), len(search_line))

                if max_len == 0:
                    continue

                distance = levenshtein(original_line, search_line)
                similarity += (1 - distance / max_len) / lines_to_check

                if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
                    break
        else:
            # No middle lines to compare, accept based on anchors
            similarity = 1.0

        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            yield yield_block(start_line, end_line)
        return

    # Multiple candidates - find best match
    best_match: tuple[int, int] | None = None
    max_similarity = -1.0

    for start_line, end_line in candidates:
        actual_block_size = end_line - start_line + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[start_line + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(original_line), len(search_line))

                if max_len == 0:
                    continue

                distance = levenshtein(original_line, search_line)
                similarity += 1 - distance / max_len

            similarity /= lines_to_check  # Average similarity
        else:
            similarity = 1.0

        if similarity > max_similarity:
            max_similarity = similarity
            best_match = (start_line, end_line)

    # Check threshold for multiple candidates
    if max_similarity >= MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD and best_match:
        start_line, end_line = best_match
        yield yield_block(start_line, end_line)


# Ordered list of replacers from strict to fuzzy
REPLACERS: list[Replacer] = [
    simple_replacer,
    line_trimmed_replacer,
    indentation_flexible_replacer,
    block_anchor_replacer,
]


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
            index = content.find(search)
            if index == -1:
                continue

            if replace_all:
                if not is_exact_match:
                    # Fuzzy match with replace_all is risky - track but don't use
                    found_fuzzy_match_for_replace_all = True
                    continue
                return content.replace(search, new_string)

            # Check for uniqueness - only replace if single occurrence
            last_index = content.rfind(search)
            if index != last_index:
                found_multiple = True
                continue  # Try next replacer for potentially more specific match

            return content[:index] + new_string + content[index + len(search) :]

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
