# Research – ReAct Manager JSON Compliance Issue
**Date:** 2025-09-18 12:00:00
**Owner:** context-engineer:research
**Phase:** Research

## Summary
The ReAct manager agent is ignoring the strict JSON-only requirement. Instead of returning a structured `{"tasks": [...]}` payload, it emits free-form prose (often prefixed with `TUNACODE DONE:`). The orchestrator then coerces the text into worker goals, leading to meaningless work and final responses that merely restate the boilerplate manager output. This breaks the manager→worker contract and prevents the loop from answering user queries.

## Impact
- Workers receive non-actionable goals (“TUNACODE DONE…” paragraphs) and fail to perform useful work.
- Final synthesis regurgitates the manager paragraph instead of summarizing real findings.
- Users see no value in `/react` runs because responses never address the original question.

## Reproduction Steps
1. Run `/thoughts on` followed by `/react gm gm what can you do?`.
2. Observe manager plan logged as plain text with `TUNACODE DONE:` instead of JSON.
3. Workers echo the prose or perform irrelevant actions (e.g., listing directories without purpose).
4. Final panel repeats the same boilerplate message.

## Root Cause Hypothesis
- Manager prompt tail is not forceful enough; the agent treats the task as a normal completion and formats with its default “TUNACODE DONE” completion protocol.
- Orchestrator `_parse_json_goals` accepts fallback text, so manager mistakes never trigger retries.
- No schema validation or retry loop ensures compliance before dispatching workers.

## Recommended Fixes
1. **Strict Validation:** Reject any manager output that cannot be parsed as JSON. Retry once with a reinforced prompt; after the second failure, raise a visible error.
2. **Prompt Tail Hardening:** Update manager tail to explicitly forbid `TUNACODE DONE`, bullet lists, or markdown fences. Provide a concrete minimal JSON example.
3. **Schema Enforcement:** Use `jsonschema` or manual checks to ensure each task has `name` and `goal`. Abort if validation fails.
4. **Tooling Support:** Optionally add a CLI `/react-debug` mode that logs manager output and validation errors for quick diagnosis.

## Next Steps
- Implement validation + retry loop in `run_react_loop` (high priority).
- Update unit/characterization tests to cover invalid manager outputs.
- Re-evaluate final synthesis prompt once workers receive real goals.

## Artifacts
- `/react gm gm what can you do?` session log (2025-09-18) showing manager and worker outputs.
