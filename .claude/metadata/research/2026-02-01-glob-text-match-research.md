# Research – Glob filesystem search_sync and block_anchor_replacer
**Date:** 2026-02-01
**Phase:** Research

## Structure
- src/tunacode/tools/ — tool implementations (glob, update_file).
- src/tunacode/tools/utils/ — shared utilities (text_match).
- src/tunacode/tools/ignore.py — ignore pattern manager used by glob.
- src/tunacode/core/agents/agent_components/ — tool registration (agent_config).
- src/tunacode/ui/renderers/tools/ — UI renderers for tool output.
- tests/unit/core/ — unit tests for text_match/update_file.

## Key Files
- src/tunacode/tools/glob.py:L30 → glob tool entrypoint.
- src/tunacode/tools/glob.py:L150 → _glob_filesystem (async wrapper for search_sync).
- src/tunacode/tools/glob.py:L161 → search_sync (filesystem traversal + matching).
- src/tunacode/tools/glob.py:L238 → _sort_matches (sorts glob results).
- src/tunacode/tools/glob.py:L255 → _format_output (formats tool output).
- src/tunacode/tools/ignore.py:L82 → IgnoreManager.
- src/tunacode/tools/ignore.py:L157 → get_ignore_manager.
- src/tunacode/tools/utils/text_match.py:L27 → SINGLE_CANDIDATE_SIMILARITY_THRESHOLD.
- src/tunacode/tools/utils/text_match.py:L28 → MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD.
- src/tunacode/tools/utils/text_match.py:L31 → levenshtein.
- src/tunacode/tools/utils/text_match.py:L162 → block_anchor_replacer.
- src/tunacode/tools/utils/text_match.py:L280 → REPLACERS list.
- src/tunacode/tools/utils/text_match.py:L288 → replace.
- src/tunacode/tools/update_file.py:L11 → replace import.
- src/tunacode/tools/update_file.py:L15 → update_file.
- src/tunacode/core/agents/agent_components/agent_config.py:L28 → glob tool import.
- src/tunacode/core/agents/agent_components/agent_config.py:L33 → update_file tool import.
- src/tunacode/ui/renderers/tools/__init__.py:L25 → render_glob import.
- src/tunacode/ui/renderers/tools/__init__.py:L36 → render_update_file import.
- tests/unit/core/test_text_match.py:L61-L86 → update_file path exercising block_anchor_replacer.

## Patterns Found
- Nested sync worker inside async wrapper: search_sync defined inside _glob_filesystem (glob.py:L150-L236).
- Pattern compilation branch for "**" globs (glob.py:L168).
- orig.startswith("**/") check appears at glob.py:L209 and glob.py:L217.
- REPLACERS registry list orders replacer functions (text_match.py:L280-L284).
- block_anchor_replacer candidate pairing uses first/last anchor indices (text_match.py:L187-L205).
- block_anchor_replacer uses single-candidate vs multi-candidate branches (text_match.py:L214-L275).

## Dependencies
- tunacode.tools.glob → imports → tunacode.tools.ignore.IgnoreManager/get_ignore_manager (glob.py:L13; ignore.py:L82/L157).
- tunacode.core.agents.agent_components.agent_config → imports → tunacode.tools.glob.glob (agent_config.py:L28).
- tunacode.core.agents.agent_components.agent_config → imports → tunacode.tools.update_file.update_file (agent_config.py:L33).
- tunacode.tools.update_file → imports → tunacode.tools.utils.text_match.replace (update_file.py:L11).
- tunacode.tools.utils.text_match.replace → uses → REPLACERS (text_match.py:L280, L317).
- tunacode.tools.utils.text_match.REPLACERS → includes → block_anchor_replacer (text_match.py:L280-L284).
- tunacode.ui.renderers.tools.__init__ → imports → render_glob/render_update_file (ui/renderers/tools/__init__.py:L25/L36).
- tests/unit/core/test_text_match.py → calls → update_file for anchor-based match scenario (test_text_match.py:L61-L86).

## Symbol Index
- glob.py: MAX_RESULTS (L15), SortOrder (L20), glob (L30), _parse_sort_order (L82), _build_ignore_manager (L90), _normalize_exclude_dir_patterns (L98), _expand_brace_pattern (L112), _glob_filesystem (L150), _sort_matches (L238), _format_output (L255).
- text_match.py: SINGLE_CANDIDATE_SIMILARITY_THRESHOLD (L27), MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD (L28), levenshtein (L31), simple_replacer (L56), line_trimmed_replacer (L65), indentation_flexible_replacer (L99), block_anchor_replacer (L162), REPLACERS (L280), replace (L288).
- update_file.py: update_file (L15).
