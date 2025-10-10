# Tool Rejection Feedback Session

- Option 3 in the tool confirmation dialog now collects user guidance via `ToolUI`, storing it on `ToolConfirmationResponse.instructions`.
- `ToolHandler.process_confirmation` detects guided aborts and calls `create_user_message`, injecting the corrective instructions into the session timeline for the agent.
- Characterization coverage keeps the legacy abort baseline while the new plan mode test ensures rejection guidance is recorded.
- No changes to approval or skip semantics; only the abort path gains the guidance recording behavior.
- REPL skips the old "Operation aborted" banner so the agent immediately focuses on the injected guidance message.
