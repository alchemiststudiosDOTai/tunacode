## Objective summary
- Update and enhance `docs/tools/react.md` to accurately and comprehensively describe the React tool, reflecting the latest implementation and its integration with the tool/agent ecosystem.

## Files to modify / reference
- **docs/tools/react.md**: Main documentation file to be updated.
- Reference: **src/tunacode/tools/react.py** (tool implementation)
- Reference: **docs/tools/architecture.md**, **docs/codebase-map/modules/tools-overview.md** (context and architecture overviews)

## Step-by-step approach
1. Audit and review the current `react.md` documentation for completeness and accuracy.
2. Cross-check every documented action, parameter, and behavior in the doc against the actual Python implementation in `react.py`.
3. Enhance explanations for the tool's purpose, ideal scenarios (multi-step workflows, debugging, planning), and its design (stateful timeline, JSON serialization).
4. Update or expand usage and code examples to match the implemented API and real agent flows.
5. Integrate architectural context: clearly reference how the tool fits with session state and the general tool system (using architecture docs as guidance).
6. Document best practices for using and resetting the scratchpad, including suggestions for iterative and transparent agent workflows.
7. Provide and update “related files” and cross-links to keep onboarding and deep dives clear for users.
8. Edit for structure, clarity, and consistency with other tooling documentation.

## Risks and considerations
- Examples may drift if the implementation is updated—recommend future review triggers tied to releases.
- Need to avoid duplication with overarching architecture docs; ensure references are accurate and concise.
- Documentation must match the latest tool signature and options to limit confusion.

## Acceptance criteria
- `docs/tools/react.md` accurately describes the React tool's current usage, capabilities, and limitations.
- All code and CLI examples are validated for accuracy and copy-paste usability.
- Relationships to state management, session persistence, and multi-step workflows are clearly explained.
- Section headers, links to related docs, and cross-references are complete and helpful.
- No contradictions with the Python implementation or session state management.
