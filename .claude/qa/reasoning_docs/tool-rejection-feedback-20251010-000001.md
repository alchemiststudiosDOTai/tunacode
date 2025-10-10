# Tool Rejection Feedback Reasoning Log

## Problem Signal
- Users selecting option 3 "No, and tell TunaCode what to do differently" triggered `UserAbortError` without collecting any guidance.
- Research document 2025-10-10_11-44-51_userabort_error_analysis.md confirmed this path was intentionally aborting but lacked the promised feedback hook.

## Approach
1. Captured a golden baseline around the existing abort path to guard regressions.
2. Introduced a failing test asserting that rejection guidance becomes a session message the next agent turn can consume.
3. Extended `ToolConfirmationResponse` with an `instructions` field, updated `ToolUI` to prompt for guidance, and routed non-empty guidance through `create_user_message` in `ToolHandler.process_confirmation`.

## Outcome
- Agents now receive explicit user instructions after a rejected tool call, removing ambiguity around option 3.
- Approval and skip logic remains unchanged; only aborts now append corrective guidance.
- Characterization coverage documents both the baseline abort behavior and the new guidance routing.
- The REPL no longer prints the legacy "Operation aborted" banner, preventing noise after guided aborts.
