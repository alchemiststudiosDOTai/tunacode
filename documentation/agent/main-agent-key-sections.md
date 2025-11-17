# Key Sections in `src/tunacode/core/agents/main.py`

This outline identifies the highest-leverage areas of the agent coordinator when scoping new requirements. The sections are ordered by the magnitude of behavior they control and the blast radius of any change.

| Priority | Section | Why It Matters | Requirement Hooks |
| --- | --- | --- | --- |
| 1 | `process_request` loop (`process_request`, lines 114+) | Central orchestrator for each CLI request: initializes session state, drives the async iteration over agent nodes, supervises tool execution, enforces iteration caps, and decides whether to finish, retry, or fall back. | All lifecycle features (new completion triggers, stop conditions, instrumentation, or response shaping) must plug in here because this is the only path executed for user-visible work. |
| 2 | Session scaffolding (`StateFacade`, `_init_context`, `_prepare_message_history`, lines 33–111) | Guarantees consistent state between runs by resetting counters, persisting request metadata, and exposing helpers for UI/debug flows. | Any requirement introducing new per-request counters or flags should extend `StateFacade.reset_for_new_request` so the state does not leak across runs. Configuration-driven behaviors must go through `StateFacade.get_setting` for consistency. |
| 3 | Productivity + React enforcement (`_iteration_had_tool_use`, `_force_action_if_unproductive`, `_maybe_force_react_snapshot`, `_ask_for_clarification`, lines 149–278) | Detects when the LLM loops without action, injects React guidance, nudges for clarification, and records forced thoughts in the run context. | Requirements that change when/how the agent self-reflects or when it must ask the user something should adjust these helpers. They are already wired into the main loop and mutate the live agent context. |
| 4 | Tool buffering + batching (`ac.ToolBuffer`, `_finalize_buffered_tasks`, lines 280–342) | Converts buffered tool-call parts into a staged batch with UI instrumentation, executes them in parallel, and reports performance data. | Any changes to tool batching policies, supported tool metadata, or UI around batched execution belong here to avoid duplicating the scheduling logic. |
| 5 | Fallback response synthesis (`_should_build_fallback`, `_build_fallback_output`, lines 344–366) | When the agent reaches iteration caps without completion, these helpers build and format the fallback multi-section summary returned to the user. | Requirements about graceful degradation, verbose summaries, or additional metadata in fail-safe responses should extend here so the behavior remains centralized. |
| 6 | Streaming + instrumentation hooks (`_maybe_stream_node_tokens`, `_iteration_had_tool_use`, logging defaults, lines 117–212) | Handles token streaming callbacks, exposes toggles for verbose UI, and computes per-iteration tooling metrics. | If a requirement needs richer streaming payloads or metric collection, extend these hooks rather than touching the inner loop: they already gate on feature availability and callbacks. |

## Additional Notes

- **React Guidance Anchors:** The CLAUDE anchors (`CLAUDE_ANCHOR[...]`) mark the code regions other components reference. Keep these identifiers stable if downstream tooling (React snapshots, delta summaries) needs to link back to the agent core.
- **UI Mutations:** All user-facing status updates go through `tunacode.ui.console`; requirements affecting UX should consider threading implications because these helpers are awaited within the primary async loop.
- **Error Surfaces:** `process_request` centralizes exception handling, translating batching errors into tool patches and logging request IDs; any new failure mode should follow the same pattern (log context, patch tool messages, then re-raise) to preserve observability.

Use this outline as the entry map when defining requirements so each modification lands next to the behavior it influences, keeping lifecycle, state, and remediation logic cohesive.
