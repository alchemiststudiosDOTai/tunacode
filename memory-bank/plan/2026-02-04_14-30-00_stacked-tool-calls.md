---
title: "Stacked Tool Call UI - Plan"
phase: Plan
date: "2026-02-04T14:30:00"
owner: "Claude"
parent_research: "memory-bank/research/2026-02-04_stacked-tool-calls.md"
git_commit_at_plan: "3a195b1b"
tags: [plan, stacked-tool-calls, ui, coding]
---

## Goal

Implement stacked/compressed tool call display when **more than 3** tool calls occur in a single response burst, rendering as compact single-line rows matching the dream UI design.

**Non-goals:**
- Option B (explicit batch tracking with batch_id/batch_total) — deferred unless timing issues emerge
- Session replay modifications — replay currently renders only user/model text; tool panels are not replayed
- Expanding stacked rows into full details — out of scope for first iteration

## Scope & Assumptions

**In scope:**
- Debounce-based batching in `src/tunacode/ui/app.py` message handler (`on_tool_result_display`)
- New stacked renderer in `src/tunacode/ui/renderers/tools/stacked.py`
- Threshold of **>3** tools triggers stacked view (kept consistent with `TOOL_BATCH_PREVIEW_COUNT = 3`)
- Integration with existing `ChatContainer.write()` mounting

**Out of scope:**
- Changes to `tool_dispatcher.py` / `orchestrator.py`
- Changes to `ToolResultDisplay` message class
- Persistent batch tracking across iterations
- Changing insertion ordering behavior (note: `ChatContainer.set_insertion_anchor()` currently isn’t used by `ChatContainer.write()`)

**Assumptions (validated against code):**
- Textual `App.set_timer(delay_seconds, callback=...)` exists (Textual 4.0.0)
- `Timer` is canceled via `.stop()` (not `.cancel()`)
- Tool completion status is available as `ToolResultDisplay.status` (no `tool.success` field exists)

## Deliverables

1. `src/tunacode/ui/renderers/tools/stacked.py` — stacked tool renderer
2. Modified `src/tunacode/ui/app.py` — buffering + debounce flush
3. Modified `src/tunacode/ui/renderers/tools/__init__.py` — export stacked renderer

## Readiness

**Preconditions:**
- Branch: `stack-tool-calls`
- Textual timer API available (`self.set_timer()`)
- Rich Panel / Group / Text composables available

**Sample input:**
- 5+ `ToolResultDisplay` messages arriving in a short burst (typical of parallel tool execution)

## Milestones

- **M1:** Buffer infrastructure — buffer list + debounce timer in app
- **M2:** Stacked renderer — compact row formatting
- **M3:** Integration — flush logic chooses stacked vs individual
- **M4:** Polish — failure styling + key-arg extraction + truncation

## Work Breakdown (Tasks)

### Task 00: UI guideline compliance (NeXTSTEP UI skill)

**Summary:** Apply NeXTSTEP UI principles for the stacked rows/panel styling.

**Owner:** Claude
**Estimate:** S
**Dependencies:** None
**Milestone:** M1

**Notes:**
- This is a UI change; follow `.claude/skills/neXTSTEP-ui/SKILL.md` while implementing styling.

---

### Task 01: Add buffer + timer infrastructure to `TextualReplApp`

**Summary:** Add private buffer list + debounce timer to the app instance.

**Owner:** Claude
**Estimate:** S
**Dependencies:** Task 00
**Milestone:** M1

**Files touched:**
- `src/tunacode/ui/app.py`

**Implementation details (grounded):**
1. Add instance attributes in `__init__`:
   - `_tool_result_buffer: list[ToolResultDisplay]`
   - `_tool_batch_timer: Timer | None`
2. Add constants:
   - `TOOL_BATCH_DEBOUNCE_SECONDS = 0.05` (50ms)
   - `TOOL_BATCH_STACK_THRESHOLD = 3`

**Acceptance test:**
- App instance has initialized buffer/timer attributes.

---

### Task 02: Refactor single-tool rendering into a helper

**Summary:** Extract the current body of `on_tool_result_display()` into a helper so flush can re-use it.

**Owner:** Claude
**Estimate:** S
**Dependencies:** Task 01
**Milestone:** M1

**Files touched:**
- `src/tunacode/ui/app.py`

**Implementation details:**
- Add `_render_tool_result(self, message: ToolResultDisplay) -> None`.
- Move the existing `tool_panel_smart(...)` + `self.chat_container.write(panel)` logic into that helper.

**Acceptance test:**
- Calling `_render_tool_result(msg)` produces the same output as the previous inline handler.

---

### Task 03: Modify `on_tool_result_display` to buffer + debounce

**Summary:** Replace immediate render with buffer append + timer reset.

**Owner:** Claude
**Estimate:** S
**Dependencies:** Task 02
**Milestone:** M1

**Files touched:**
- `src/tunacode/ui/app.py`

**Implementation details (Textual 4.0.0 specifics):**
1. Append message to `_tool_result_buffer`.
2. If `_tool_batch_timer` exists, call `_tool_batch_timer.stop()`.
3. Start a new timer: `self.set_timer(TOOL_BATCH_DEBOUNCE_SECONDS, self._flush_tool_results)`.

**Acceptance test:**
- Multiple rapid tool results do not render immediately; they render after debounce.

---

### Task 04: Create stacked renderer module

**Summary:** New renderer that formats multiple tools as compact rows.

**Owner:** Claude
**Estimate:** M
**Dependencies:** Task 00
**Milestone:** M2

**Files touched:**
- `src/tunacode/ui/renderers/tools/stacked.py` (new)
- `src/tunacode/ui/renderers/tools/__init__.py`

**Implementation details:**
1. Create `render_stacked_tools(tools: list[ToolResultDisplay], *, max_line_width: int) -> Panel`.
2. Add helper `_extract_key_arg(tool_name: str, args: dict[str, Any] | None) -> str`.
3. Row format (example): `> {tool_name:<12} {key_arg}`.
4. Use Rich `Group` to compose rows into a single `Panel`.
5. Match panel width to other tool panels for visual alignment (use `tool_panel_frame_width(max_line_width)` from existing panel helpers if appropriate).
6. Export from `__init__.py`.

**Acceptance test:**
- `render_stacked_tools([...5 tools...], max_line_width=...)` returns a `Panel` containing 5 compact rows.

---

### Task 05: Implement `_flush_tool_results` batching logic

**Summary:** Timer callback decides stacked vs individual rendering.

**Owner:** Claude
**Estimate:** M
**Dependencies:** Task 03, Task 04
**Milestone:** M3

**Files touched:**
- `src/tunacode/ui/app.py`

**Implementation details:**
1. Create `_flush_tool_results(self) -> None`.
2. Snapshot buffer locally, then clear buffer early (fail-fast / avoid re-entrancy surprises).
3. Compute `max_line_width = self.tool_panel_max_width()`.
4. If `len(batch) > TOOL_BATCH_STACK_THRESHOLD`:
   - render one panel via `render_stacked_tools(batch, max_line_width=max_line_width)`
   - `self.chat_container.write(panel)`
5. Else:
   - iterate and call `_render_tool_result(msg)` per tool
6. Set `_tool_batch_timer = None` after flush.

**Acceptance test:**
- 5 tool results render as 1 stacked panel.
- 2 tool results render as 2 individual panels.

---

### Task 06: Failure styling + key-arg extraction

**Summary:** Style failed tool rows and show key argument per tool type.

**Owner:** Claude
**Estimate:** S
**Dependencies:** Task 04
**Milestone:** M4

**Files touched:**
- `src/tunacode/ui/renderers/tools/stacked.py`

**Implementation details (grounded in message shape + tool signatures):**
1. Determine failure using `ToolResultDisplay.status` (e.g., `status != "completed"`).
2. Apply red styling for failed rows and append a short suffix (e.g., `" [FAILED]"`).
3. Key argument mapping based on current tool signatures:
   - `glob` -> `pattern`
   - `read_file` -> `filepath`
   - `list_dir` -> `directory`
   - `grep` -> `pattern` (optionally include directory if present)
   - `bash` -> `command`
   - `write_file` / `update_file` -> `filepath`
   - `web_fetch` -> `url` (fallback to first present key)
4. Truncate long values (~40 chars) with ellipsis.
5. Handle missing args gracefully (empty string).

**Acceptance test:**
- A non-completed tool status row renders red and includes `[FAILED]`.
- Rows show correct primary argument for `glob`, `read_file`, `bash`.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Debounce flush before all tool returns arrive | Medium | Some tools render individually | Increase debounce (e.g., 0.10s) if observed |
| Timer stop/start edge cases | Low | Missed flush | Clear timer ref after flush; stop old timer before starting new |
| Buffer grows unbounded if flush crashes | Low | Memory leak | Clear buffer early in `_flush_tool_results` and fail loud |
| Misaligned panel width vs tool panels | Medium | UI inconsistency | Pass `max_line_width` and set panel width accordingly |

## Test Strategy

- Manual visual verification:
  - Trigger 5–10 tool calls in one model response (glob + multiple read_file + list_dir).
  - Verify:
    - >3 => stacked panel
    - <=3 => individual tool panels
    - Failed tool => red row + suffix

## References

- Research doc: `memory-bank/research/2026-02-04_stacked-tool-calls.md`
- Dream UI: `docs/images/dream-ui/tunacode-cli-response.png`
- Current handler: `src/tunacode/ui/app.py:on_tool_result_display`
- Tool panel routing: `src/tunacode/ui/renderers/panels.py:tool_panel_smart`
- Tool batch threshold source: `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py:TOOL_BATCH_PREVIEW_COUNT`

## Final Gate

**Output summary:**
- Plan path: `memory-bank/plan/2026-02-04_14-30-00_stacked-tool-calls.md`
- Milestone count: 4
- Task count: 7
- Tasks ready for coding: All (sequential within milestones)

**Next command:** `/context-engineer:execute "memory-bank/plan/2026-02-04_14-30-00_stacked-tool-calls.md"`
