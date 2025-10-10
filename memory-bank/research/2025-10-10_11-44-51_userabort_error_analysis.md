# Research – UserAbortError Analysis
**Date:** 2025-10-10
**Owner:** Claude Code
**Phase:** Research

## Goal
Explain why selecting option 3 ("No, and tell TunaCode what to do differently") causes a UserAbortError and whether this is the expected behavior.

## Findings

### Relevant Files & Why They Matter:
- `/root/tunacode/src/tunacode/exceptions.py:36-39` - Contains the UserAbortError definition
- `/root/tunacode/src/tunacode/cli/repl_components/tool_executor.py:87` - Where the error is raised during tool execution
- `/root/tunacode/src/tunacode/ui/tool_ui.py:136-137, 192-193` - Where option 3 triggers the abort response
- `/root/tunacode/src/tunacode/core/tool_handler.py:75-89` - Logic for processing confirmation responses
- `/root/tunacode/src/tunacode/core/agents/agent_components/node_processor.py:474` - Where the tool callback fails and logs the error

### Tool Execution Flow:
1. **Tool Request**: Bash tool execution is requested for the rag-cli.sh command
2. **Confirmation Dialog**: TunaCode shows confirmation prompt with 3 options
3. **User Selection**: Option 3 is selected
4. **Response Processing**: UI returns `ToolConfirmationResponse(approved=False, abort=True)`
5. **Error Raising**: tool_executor.py raises `UserAbortError("User aborted.")`
6. **Error Propagation**: Error bubbles up through node_processor and is logged

## Key Patterns / Solutions Found

### The UserAbortError is EXPECTED BEHAVIOR
- **Not a bug**: Option 3 is designed to abort tool execution
- **UI inconsistency**: The prompt text suggests feedback collection but only implements abort
- **Graceful handling**: Error is caught and displays "Operation aborted by user" message

### Option Behaviors:
- **Option 1**: Execute tool normally (approved=True, abort=False)
- **Option 2**: Execute and skip future confirmations (approved=True, skip_future=True)
- **Option 3**: Abort execution (approved=False, abort=True)

### Error Handling Pattern:
The UserAbortError is consistently handled across the codebase:
- REPL catches and continues with muted message
- Main agent catches and re-raises to stop processing
- Tool messages are patched with abort notification

## Knowledge Gaps

### Missing Functionality:
The UI text "tell TunaCode what to do differently" implies a feedback mechanism that doesn't exist. There's no implementation for:
- Collecting user corrections or alternative approaches
- Processing user feedback about tool execution
- Modifying agent behavior based on user preferences

### UX Issue:
Users expect to provide input/corrections when selecting option 3, but only receive an abort message.

## Additional Search Results

- `grep -ri "UserAbortError" /root/tunacode/src/` - Found 12 occurrences across 6 files
- `grep -ri "tell.*differently" /root/tunacode/src/` - Only appears in UI confirmation text

## References

### Key Code Locations:
- Error definition: `/root/tunacode/src/tunacode/exceptions.py:36-39`
- Error raised: `/root/tunacode/src/tunacode/cli/repl_components/tool_executor.py:87`
- Option 3 handler: `/root/tunacode/src/tunacode/ui/tool_ui.py:136-137`
- Error logged: `/root/tunacode/src/tunacode/core/agents/agent_components/node_processor.py:474`

### Test Coverage:
- Tool confirmation tests: `/root/tunacode/tests/characterization/ui/test_tool_confirmations.py`
- Error handling tests: `/root/tunacode/tests/characterization/repl/test_error_handling.py`

## Conclusion

The UserAbortError when selecting option 3 is **working as designed** - it's meant to abort tool execution. However, there's a significant UX disconnect between the UI promise ("tell TunaCode what to do differently") and the actual implementation (simple abort). This creates confusion for users who expect to provide feedback or alternative instructions.

**Recommendation**: Either implement the feedback collection mechanism as promised, or update the UI text to accurately reflect that option 3 is just an abort operation.
