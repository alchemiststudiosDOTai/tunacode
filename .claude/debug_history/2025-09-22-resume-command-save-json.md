Date: 2025-09-22 22:45:00
Component: ResumeCommand / session_utils

Error:
- During tests, saving session failed with "Object of type set is not JSON serializable" followed by a corrupted JSON read on load.
- Root cause: `files_in_context` stored as a `set` in SessionState was written directly to JSON.

Resolution:
- Normalized `files_in_context` to a sorted list in `_collect_essential_state` before JSON dump.
- Re-ran tests: resume roundtrip passed; unrelated grep test remains failing (pre-existing).

Files:
- src/tunacode/utils/session_utils.py: normalize set -> list for `files_in_context`.

Notes:
- Kept persistence minimal (messages, user_config, current_model, session_id, total_cost, files_in_context, session_total_usage).
