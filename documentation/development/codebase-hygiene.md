## Agent API Surface

- tech-docs-maintainer (short): main orchestration now imports helper APIs from `tunacode.core.agents.agent_components`; CLI code should patch via `tunacode.core.agents` so test mocks stay aligned with the single source of truth.
