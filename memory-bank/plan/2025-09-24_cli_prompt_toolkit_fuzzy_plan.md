# Plan – Prompt Toolkit Fuzzy Completion Reintegration
**Date:** 2025-09-24
**Owner:** Claude Coding Agent
**Status:** Draft

**Progress Snapshot (2025-09-24 18:20 UTC)**
- Red ✅ – Characterization tests recreated and failing baseline captured.
- Green ✅ – prompt_toolkit fuzzy completions implemented; targeted tests pass via `uv run`.
- Blue ▢ – Refactor/documentation cleanup and broader regression testing still pending.

## 1. Objective & Success Criteria
- Reintroduce fuzzy matching for command names and @file references using `prompt_toolkit`'s native fuzzy completers (`FuzzyCompleter`, `FuzzyWordCompleter`).
- Deliver behavior that restores typo tolerance and mid-string matching while preserving existing prefix ordering expectations.
- Avoid introducing new source modules; limit scope to targeted edits with clear fail-fast semantics and explicit typing.

Success is measured by:
1. A green characterization test capturing fuzzy suggestions for both slash commands and @file references.
2. Manually verified CLI experience showing fuzzy suggestions ordered ahead of less-relevant results without performance regressions.
3. Updated documentation and knowledge base entries reflecting the renewed behavior.

## 1.1 Existing Prompt Toolkit Usage (proof)
- `src/tunacode/ui/completers.py:6-16` already imports `prompt_toolkit.completion` classes and integrates them into the CLI completer pipeline.
- `src/tunacode/ui/prompt_manager.py:6-12` builds the primary prompt session using `prompt_toolkit` components (`PromptSession`, `KeyBindings`, `Completer`).
- `src/tunacode/ui/model_selector.py:5-21` constructs a rich TUI with `prompt_toolkit` layout primitives, confirming the library underpins current interactive flows.
- `src/tunacode/cli/repl.py:11-32` depends on `prompt_toolkit.application.run_in_terminal` to coordinate CLI rendering, demonstrating tight integration today.

## 2. Implementation Surfaces (no new files)
| Area | File | Change Intent |
| --- | --- | --- |
| Command registry completer wiring | `src/tunacode/cli/commands/registry.py` | Inject `FuzzyCompleter` around existing command lists when building the prompt-toolkit completer, while keeping fallback error handling fail-fast. |
| REPL command completion bootstrap | `src/tunacode/cli/repl.py` & `src/tunacode/ui/completers.py` | Introduce prompt toolkit fuzzy wrappers for both slash-command and file reference completers; ensure ordering logic stays explicit and hidden state removed. |
| UI completers | `src/tunacode/ui/completers.py` | Refactor `CommandCompleter`/`FileReferenceCompleter` to delegate fuzzy scoring to `prompt_toolkit`, extracting symbolic constants for cutoffs and match limits. |
| Metadata & anchors | `.claude/memory_anchors/anchors.json`, `.claude/delta_summaries/behavior_changes.json` | Update anchors to capture new fuzzy integration touch-points; document behavior shift.
| Documentation | `documentation/changelog/CHANGELOG.md`, `TODO.md`, `memory-bank/research/2025-09-24_fuzzy_logic_implementation_analysis.md` | Refresh changelog/TODO to reflect reintroduction; append research updates.

## 3. Test-First Strategy (single failing test)
- Add characterization test `tests/characterization/test_cli_fuzzy_matching.py::TestPromptToolkitFuzzy::test_fuzzy_suggests_command` that spins up the CLI completer, feeds a typo like `"/hep"`, and asserts the fuzzy candidate list includes `/help` while prefix-only logic would fail.
- Extend same test module with `test_fuzzy_file_reference_prioritizes_files` to verify `@tst_example.py` suggests `test_example.py` via fuzzy selection, ensuring files precede directories.
- Run the new test in isolation with `uv run --python .venv/bin/python -m pytest tests/characterization/test_cli_fuzzy_matching.py` expecting RED initially.

## 4. Execution Timeline (TDD Red → Green → Blue)
1. **Red**
   - Recreate `tests/characterization/test_cli_fuzzy_matching.py` with updated prompt-toolkit based expectations.
   - Exercise CLI completer wiring without touching implementation to confirm failure.
2. **Green**
   - Layer `FuzzyCompleter` around command and file completers; expose configuration constants.
   - Verify green by re-running the isolated test, then full suite via `uv run hatch run test` to confirm no regressions.
3. **Blue**
   - Refine duplicated logic, extract helper functions where intent is repeated, and update documentation/metadata/anchors.

**Cross-ecosystem follow-ups (deferred):**
- Auto-prioritise roots by inspecting ecosystem markers (e.g., `package.json`, `CMakeLists.txt`) instead of hard-coding Python paths.
- Extend ignore lists to cover `node_modules`, `build`, `dist`, `target`, and other non-Python artifacts.
- Consider optional metadata-driven weighting so language-specific extensions (.js/.ts, .cpp/.hpp) bubble up appropriately.

## 5. Risks & Mitigations
- **Performance degradation with large command/file sets** → Use `ThreadedCompleter` if latency is observed; document fallback in TODO.
- **Inconsistent ordering vs. historical expectations** → Maintain explicit post-processing to enforce file-before-dir rules.*
- **Prompt Toolkit version drift** → Confirm current version supports `FuzzyCompleter` and capture requirement in research note if upgrade needed.

## 6. Open Questions
1. Should we gate fuzzy behavior behind a user config flag for power users who prefer prefix-only matching?
2. Do we need to resurrect additional fuzzy tests (e.g., for models registry) or limit surface area to CLI interactions?
3. Are there accessibility considerations (e.g., highlight styling) that require Rich integration updates?

## 7. Next Immediate Action
- Implement RED step: restore the characterization test, then execute `uv run --python .venv/bin/python -m pytest tests/characterization/test_cli_fuzzy_matching.py` to capture the failing baseline before touching implementation code.

*Maintain file-before-directory ordering by combining prompt-toolkit fuzzy scoring with deterministic post-sort tied to symbolic constants.


 - Clarify Objective: Target a detection + weighting layer that broadens ecosystem coverage while keeping current Python-first flow intact when nothing else matches.
   okay again this is the issue we dont know whart codin g languae they will use

- Inventory Current State: Document today’s hardcoded paths/skip lists in src/tunacode/ui/completers.py so we know exactly what must stay as the Python fallback.
  - Introduce Ecosystem Schema: Define a small EcosystemProfile dataclass or typed dict storing markers, roots, skips, extensions, metadata tags; start with just
  Python + JS/TS + C++ to keep diff tiny.
  - Add Detection Utility: Implement _detect_ecosystem() that walks upward a bounded depth, counts marker hits per profile, and returns the best match (ties fall back
  to Python profile). Cache result on the completer instance.
  - Refactor Root/Skip Providers: Swap the current module-level constants for a profile = self._detect_or_default() call that feeds priority roots, skip prefixes, and
  extension sets into the existing traversal logic. Preserve ordering rules from the behavior change log.
  - Lightweight Metadata Hook: When building Completion, append the profile’s metadata hint if defined for the file extension; no UI overhaul required.
  - Optional Config Ingestion: Allow a simple TOML override (e.g., .tunacode-completer.toml) that merges into the selected profile. Keep parsing isolated so it can be
  skipped if file absent.
  - Testing Strategy: Extend characterization tests with tmpdir fixtures for JS and C++ layouts; ensure Python baseline stays green. Cover config override and no-
  marker fallback. Run via hatch run test.
  - Knowledge Base Updates: Plan to record new anchors around detection logic, refresh .claude/semantic_index/function_call_graphs.json, and log behavior/API shifts in
  delta_summaries/behavior_changes.json once code lands.
