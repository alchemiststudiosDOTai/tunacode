---
title: "renderer taxonomy cleanup research findings"
link: "renderer-taxonomy-cleanup-research"
type: research
research_type: "explore"
commitment_status: "decision-support"
research_goal: "Map current exception renderer taxonomy entries against actual TunaCode exception definitions and raise sites."
ontological_relations:
  - relates_to: [[exceptions-py-research]]
tags: [research, explore, exceptions, renderer]
uuid: "59d8825f-fd8f-4c42-995a-034d3a2ee556"
created_at: "2026-04-27T14:34:08-05:00"
---

## Research Intent
- Research type: `explore`
- Commitment status: `decision-support`
- Goal: identify which `src/tunacode/ui/renderers/errors.py` taxonomy entries correspond to current exception definitions and production raise sites.
- Out of scope: source edits to the renderer, deletion decisions for `src/tunacode/exceptions.py`, and interface design beyond the current renderer taxonomy.

## Question
- Which entries in `ERROR_SEVERITY_MAP`, `DEFAULT_RECOVERY_COMMANDS`, and renderer pattern matching are backed by currently raised TunaCode exceptions?

## Structure
- `src/tunacode/ui/renderers/errors.py:7` imports exception classes from `tunacode.exceptions`.
- `src/tunacode/ui/renderers/errors.py:23` defines `ERROR_SEVERITY_MAP` keyed by exception class name strings.
- `src/tunacode/ui/renderers/errors.py:41` defines `_extract_tunacode_exception_context`.
- `src/tunacode/ui/renderers/errors.py:57` defines `_extract_tunacode_exception_metadata`.
- `src/tunacode/ui/renderers/errors.py:73` defines `DEFAULT_RECOVERY_COMMANDS` keyed by exception class name strings.
- `src/tunacode/ui/renderers/errors.py:102` defines `render_exception(exc)`.

## Key Files
- `src/tunacode/ui/renderers/errors.py:23` -> renderer severity taxonomy.
- `src/tunacode/ui/renderers/errors.py:73` -> renderer default recovery command taxonomy.
- `src/tunacode/ui/app.py:232`, `src/tunacode/ui/app.py:371`, `src/tunacode/ui/app.py:379` -> production calls to `render_exception`.
- `tests/unit/core/test_provider_error_surfacing.py:31` -> tests `ERROR_SEVERITY_MAP["AgentError"]`.
- `tests/unit/core/test_provider_error_surfacing.py:40`, `tests/unit/core/test_provider_error_surfacing.py:56`, `tests/unit/core/test_provider_error_surfacing.py:78` -> tests `render_exception` with active exception classes.

## Renderer Taxonomy Entries
- `ToolExecutionError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:24`.
  - Context match at `src/tunacode/ui/renderers/errors.py:43`.
  - Metadata match at `src/tunacode/ui/renderers/errors.py:61`.
  - Production raise sites exist in tool wrappers, including `src/tunacode/tools/bash.py:195`, `src/tunacode/tools/web_fetch.py:243`, `src/tunacode/tools/discover.py:74`, `src/tunacode/tools/read_file.py:71`, and `src/tunacode/tools/utils/file_errors.py:48`.
- `FileOperationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:25`.
  - Context match at `src/tunacode/ui/renderers/errors.py:45`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:87`.
  - Production raise sites exist in `src/tunacode/tools/utils/file_errors.py:25`, `src/tunacode/tools/utils/file_errors.py:32`, and `src/tunacode/tools/utils/file_errors.py:39`.
- `AgentError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:26`.
  - Metadata match at `src/tunacode/ui/renderers/errors.py:66`.
  - Production raise site exists at `src/tunacode/core/agents/agent_components/agent_streaming.py:456`.
- `GitOperationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:27`.
  - Context match at `src/tunacode/ui/renderers/errors.py:47`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:91`.
  - No production raise site was found outside `src/tunacode/exceptions.py`.
- `GlobalRequestTimeoutError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:28`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:95`.
  - Production raise site exists at `src/tunacode/core/agents/main.py:85`.
- `ContextOverflowError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:29`.
  - Context match at `src/tunacode/ui/renderers/errors.py:49`.
  - Production raise site exists at `src/tunacode/core/agents/main.py:231`.
- `ToolBatchingJSONError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:30`.
  - No production raise, import, or test reference was found outside `src/tunacode/exceptions.py` and the renderer string key.
- `AuthenticationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:31`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:82`.
  - No `AuthenticationError` definition or production raise site was found in `src`, `tests`, `docs`, or `scripts`.
- `ConfigurationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:32`.
  - Metadata match at `src/tunacode/ui/renderers/errors.py:64`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:74`.
  - Production raise sites exist in `src/tunacode/configuration/user_config.py:68`, `src/tunacode/configuration/user_config.py:70`, `src/tunacode/configuration/user_config.py:74`, `src/tunacode/configuration/user_config.py:270`, `src/tunacode/configuration/user_config.py:274`, and `src/tunacode/configuration/user_config.py:278`.
- `ModelConfigurationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:33`.
  - Context match at `src/tunacode/ui/renderers/errors.py:49`.
  - Default recovery commands at `src/tunacode/ui/renderers/errors.py:78`.
  - No production raise site was found outside `src/tunacode/exceptions.py`.
- `ValidationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:34`.
  - Metadata match at `src/tunacode/ui/renderers/errors.py:65`.
  - No production raise site was found for `tunacode.exceptions.ValidationError`; `src/tunacode/core/session/state.py:20` imports `pydantic.ValidationError`.
  - Tests instantiate `tunacode.exceptions.ValidationError` in `tests/unit/core/test_exceptions.py:33` and `tests/unit/core/test_exceptions.py:93`.
- `SetupValidationError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:35`.
  - Context match at `src/tunacode/ui/renderers/errors.py:51`.
  - No production raise site was found outside `src/tunacode/exceptions.py`.
- `UserAbortError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:36`.
  - Production raise sites exist in tool abort paths: `src/tunacode/tools/hashline_edit.py:273`, `src/tunacode/tools/write_file.py:66`, `src/tunacode/tools/bash.py:182`, `src/tunacode/tools/web_fetch.py:227`, `src/tunacode/tools/discover.py:60`, and `src/tunacode/tools/read_file.py:146`.
  - Production catch site exists at `src/tunacode/ui/main.py:86`.
- `StateError`
  - Severity key at `src/tunacode/ui/renderers/errors.py:37`.
  - No production raise, import, or test reference was found outside `src/tunacode/exceptions.py` and the renderer string key.

## Patterns Found
- The renderer uses string keys for severity and recovery commands, while context and metadata extraction use class pattern matching.
- `ERROR_SEVERITY_MAP` contains entries for currently raised exceptions, defined-but-unraised exceptions, and one undefined exception name.
- `DEFAULT_RECOVERY_COMMANDS` contains entries for currently raised exceptions and defined/undefined exceptions with no production raise sites.
- `render_exception` defaults missing severity keys to `"error"` at `src/tunacode/ui/renderers/errors.py:104`.
- `render_exception` defaults missing recovery commands to `None` after lookup at `src/tunacode/ui/renderers/errors.py:113`.
- The renderer strips formatted message text by splitting on `"Fix: "`, `"Suggested fix: "`, and `"Recovery commands:"` at `src/tunacode/ui/renderers/errors.py:117`.

## Current Raise-Site Groups
- Currently raised and renderer-classified: `ToolExecutionError`, `FileOperationError`, `AgentError`, `GlobalRequestTimeoutError`, `ContextOverflowError`, `ConfigurationError`, `UserAbortError`.
- Renderer-classified but no production raise site found: `GitOperationError`, `ToolBatchingJSONError`, `ModelConfigurationError`, `ValidationError`, `SetupValidationError`, `StateError`.
- Renderer-classified but no exception definition found: `AuthenticationError`.

## Test Surface
- `tests/unit/core/test_provider_error_surfacing.py:30` asserts `AgentError` exists in `ERROR_SEVERITY_MAP`.
- `tests/unit/core/test_provider_error_surfacing.py:37` renders `AgentError`.
- `tests/unit/core/test_provider_error_surfacing.py:53` renders `ToolExecutionError`.
- `tests/unit/core/test_provider_error_surfacing.py:75` renders `ContextOverflowError`.
- No test currently asserts absence of stale renderer taxonomy keys.
