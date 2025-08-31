# Prompt XML

Tool Prompt System Architecture Report

## Executive Summary

TunaCode’s tool system currently spreads definitions across three independently-evolved layers, causing maintenance overhead and consistency risks. Unifying these layers behind a single, typed source of truth would simplify changes, improve reliability, and reduce runtime overhead.

## Current Three-Layer Architecture

1) System Prompt Layer (`src/tunacode/prompts/system.md`)
   - Human-readable instructions for the AI
   - Tool examples and batching strategies
   - ~360 lines of hardcoded documentation (file is 360 lines)

2) XML Schema Layer (`src/tunacode/tools/prompts/*.xml`)
   - Parameter definitions and validation rules
   - 11 separate XML files (loaded dynamically at runtime via `xml_helper.py`)
   - Examples: `grep_prompt.xml`, `glob_prompt.xml`, `read_file_prompt.xml`, `write_file_prompt.xml`

3) Python Implementation Layer (`src/tunacode/tools/*.py`)
   - Actual execution logic per tool, built atop `BaseTool` in `src/tunacode/tools/base.py`
   - `BaseTool.get_tool_schema()` returns OpenAI-function-like schema combining description (prompt) and parameters
   - Parameter schemas are implemented in code per tool (effectively hardcoded fallbacks), optionally complemented by XML via `xml_helper.py`

## Key Problems Identified

- __Triple maintenance__: Any tool change requires edits in system prompt, XML, and Python code
- __Inconsistent descriptions__: Tool text can diverge between system prompt, XML, and code
- __Runtime overhead__: XML parsing occurs at runtime (even with caching)
- __No single source of truth__: Each layer can drift independently

## Critical Finding: Registration Flow

- Tools are registered in `src/tunacode/core/agents/agent_components/agent_config.py` around lines 244–266, where tool callables are wrapped as `pydantic_ai.Tool` objects for the `Agent`.
- Descriptions ultimately come from tool prompts (e.g., via `BaseTool.prompt()`), which may draw from XML (`xml_helper.py`) or inline code, creating potential mismatches with XML/system prompt text.

## Existing Unification Building Blocks

- __`src/tunacode/tools/xml_helper.py`__: Centralized XML loading with caching
- __`src/tunacode/tools/schema_assembler.py`__: Dynamic schema assembly for OpenAI-style function schemas
- __`src/tunacode/tools/base.py` (`BaseTool`)__: Prompt hooks and schema generation entry points

## Recommended Architecture (Single Source of Truth)

Define tools with a single typed definition that drives all layers: system prompt snippets, OpenAI/Anthropic function schemas, and Python execution. Conceptually:

```python
@tool_definition(
    name="grep",
    category="READ_ONLY",  # Drives batching and safety policies
    description="Search file contents"
)
class GrepTool:
    pattern: str = Field(description="Search pattern")
    directory: str = Field(default=".", description="Directory to search")

    examples = [
        ("grep('TODO')", "Find all TODO comments"),
    ]

    async def execute(self, ctx):
        # Implementation
        ...
```

This enables:
- __Automatic system prompt generation__ from `name`, `description`, `examples`, and `category`
- __Dynamic OpenAI/Anthropic schemas__ derived from the typed fields
- __Consistency across layers__ (prompt, schema, and code share one definition)
- __Better type checking__ and editor support
- __Simpler tool additions__ (one place to define everything)

## Impact Assessment

- __Migration scope__: 11 XML prompt files and each corresponding Python tool
- __Batching rules__: Replace hardcoded lists with category-driven policies. Today, read-only grouping exists as `READ_ONLY_TOOLS` in `src/tunacode/constants.py`; derive from `category` instead.
- __Agent wiring__: `agent_config.py` continues wrapping tools, but schemas/prompts will be pulled consistently from the unified definitions.

## Phased Migration Plan

1) __Introduce decorator + registry__ (no behavior changes). Allow tools to self-describe fields, description, examples, and category.
2) __Bridge system prompt generation__: Generate per-tool snippets from registry; include them in `system.md` build or at agent creation time.
3) __Adopt schema assembler__: Point `schema_assembler.py` and tool registration to the unified registry for parameters and descriptions.
4) __Pilot migration__: Port 1–2 tools (e.g., `grep`, `read_file`) to validate types, prompts, and runtime behavior.
5) __Migrate all tools__: Convert remaining tools; keep XML parsing as a fallback during the transition.
6) __Remove XML layer__: Once parity is verified, delete XML files and corresponding loaders.
7) __Finalize docs/tests__: Update docs and expand tests to cover prompt text, schema correctness, and execution paths.

## Risks and Mitigations

- __Schema drift during transition__: Keep XML fallback and add a consistency check that compares generated vs. legacy schemas.
- __Prompt text regressions__: Snapshot current `system.md` segments and assert generated prompt contains required guidance/examples.
- __Unexpected runtime behavior__: Introduce end-to-end tests per tool before and after migration.
- __Tool categorization mistakes__: Enforce categories via enum; add tests to validate batching/safety rules.

## Success Criteria

- __Single source of truth__: Tool name, description, parameters, examples, and category defined once
- __Zero runtime XML parsing__: All prompts/schemas generated from definitions
- __Consistency__: No mismatches between system prompt and tool schemas
- __Developer velocity__: New tool added with one definition, auto-wired into agent with correct batching rules

## Format Considerations: XML vs JSON

- __Why XML can be preferable for authoring__:
  - Rich tag semantics and attributes for prompt structure and intent
  - Supports comments and namespaces for clarity and disambiguation
  - Strong schema validation with XSD; deterministic transforms with XSLT
  - Well-suited for mixed content (text + structure) in prompts/specs
- __Why JSON is preferable at runtime__:
  - Native fit for provider function-calling schemas (OpenAI/Anthropic)
  - Lightweight parsing with ubiquitous tooling
  - Minimal overhead when embedded/generated directly
- __Plan impact__:
  - Keep a single typed definition as the source of truth
  - Optionally author in XML for ergonomics; generate JSON schemas and system prompt text at build-time
  - Avoid runtime XML parsing by precompiling XML to code/JSON (replace runtime reads in `src/tunacode/tools/xml_helper.py`)
  - Continue schema assembly via `src/tunacode/tools/schema_assembler.py`

## Guide: Creating Effective Implementation Plans

This guide outlines a collaborative, research-driven process for creating detailed and actionable implementation plans. The goal is to move from ambiguity to clarity, reduce risk, and create a shared understanding of the work before a single line of code is written.

### Core Principles

1. **Be Skeptical, Be Thorough:** Don't take requirements at face value. Question assumptions, anticipate edge cases, and identify potential issues early. Verify your understanding by investigating the actual codebase, not just documentation.
2. **Understand Before You Plan:** The most common planning failure is building on a flawed understanding of the current state. Invest significant time in research before proposing solutions. An hour of research can save a week of rework.
3. **Collaborate and Iterate:** A plan is not a solo activity. It's a conversation. Share findings, propose options, and get buy-in at each stage. The plan should evolve with feedback, not be delivered as a final, unchangeable artifact.
4. **Be Explicit and Precise:** A good plan leaves no room for interpretation. Use specific file paths, define clear success criteria, and explicitly state what is out of scope. This prevents scope creep and ensures everyone is aligned.
5. **Plan for Verification:** A plan is useless if you can't prove it's complete. Define exactly how success will be measured, separating automated checks from the manual validation that requires human judgment.

### The Planning Process

Follow these phases to move from an initial idea to a concrete, actionable plan.

#### Phase 1: Discovery & Analysis

The goal of this phase is to develop an informed understanding of the task and its context.

1. **Gather All Context:** Collect and read all relevant materials: the ticket, design documents, related research, and conversations.
2. **Investigate the Codebase:** Before asking any questions, dive into the code.
   - Locate the relevant source files, configurations, and tests.
   - Trace the data flow and identify key functions or components related to the task.
   - Understand the existing patterns, conventions, and constraints in that part of the system.
3. **Synthesize and Ask Smart Questions:** Now, present your understanding to the team and ask targeted questions that your research couldn't answer.
   - **Start with what you know:** "Based on my review of `[file:line]`, I understand we need to [accurate summary]. I've found that the current system [relevant detail]."
   - **Ask specific, informed questions:** Avoid vague questions like "How should I do this?" Instead, ask questions that require technical judgment or business clarification, such as:
     - "I see two patterns for this in the code. Should I follow the approach in `[module A]` or `[module B]`?"
     - "What should happen if a user provides an invalid input `[edge case]`?"
     - "Is performance a primary constraint for this feature?"

#### Phase 2: Deep Dive & Design Options

With a clear understanding, the next step is to explore potential solutions.

1. **Conduct Focused Research:** Investigate specific implementation details. Look for similar features in the codebase to use as a model. Research any new libraries or technologies required.
2. **Propose and Debate Solutions:** Don't settle on the first idea. Document at least two viable options and present them to the team.
   - **Option A:** [Brief description]
     - **Pros:** [e.g., Faster to implement, follows existing patterns]
     - **Cons:** [e.g., Less scalable, introduces tech debt]
   - **Option B:** [Brief description]
     - **Pros:** [e.g., More robust, better performance]
     - **Cons:** [e.g., Requires significant refactoring, more complex]
3. **Align on an Approach:** Discuss the trade-offs and collectively decide on the best path forward. This decision is the foundation for the detailed plan.

#### Phase 3: Structuring and Writing the Plan

Now, document the chosen approach in a structured format.

1. **Outline the Phases:** First, break the implementation into logical, sequential phases. Share this high-level outline for feedback before writing the details.
   - Example: 1. Database Schema, 2. Backend Logic, 3. API Endpoint, 4. Frontend UI.
2. **Write the Detailed Plan:** Use a standard template (see below) to flesh out each phase. Be meticulous. Include file paths, code snippets for complex logic, and clear descriptions of the required changes.
3. **Define Unambiguous Success Criteria:** For each phase, define how to verify its completion. This is the most critical part of the plan.
   - **Automated Verification:** Commands that can be run to prove correctness (e.g., `make test`, `npm run lint`, a `curl` command to a new endpoint).
   - **Manual Verification:** A checklist for a human to follow to test things that can't be automated (e.g., "Verify the new button appears correctly on mobile" or "Confirm the performance is acceptable with 1000+ items").
4. **Ensure No Open Questions:** If you encounter an unresolved question while writing, stop. Get it answered before continuing. The final plan must be a complete and actionable guide, not a list of questions.

#### Phase 4: Review and Refine

1. **Share the Draft:** Post the complete draft plan for team review.
2. **Request Specific Feedback:** Guide the review process by asking targeted questions:
   - "Are the phases properly scoped and ordered?"
   - "Are the success criteria specific enough to be tested?"
   - "Have I missed any technical details, edge cases, or dependencies?"
3. **Iterate:** Update the plan based on feedback. Continue this refinement loop until the team is confident in the plan.

### Standard Implementation Plan Template

```markdown
# [Feature/Task Name] Implementation Plan

## 1. Overview
*A brief, one-sentence description of what we are building and why it's important.*

## 2. Current State & Key Discoveries
*What exists now, what's missing, and what key constraints or patterns were discovered during research. Include links to specific files or line numbers.*

## 3. Desired End State
*A clear specification of the desired state after this plan is complete and how to verify it.*

## 4. What We're NOT Doing
*Explicitly list out-of-scope items to prevent scope creep.*

## 5. Implementation Approach
*A high-level summary of the chosen strategy and the reasoning behind it.*

---

## Phase 1: [Descriptive Name]

### Overview
*What this phase accomplishes and why it comes first.*

### Changes Required:
- **File:** `path/to/file.ext`
- **Changes:** [Summary of changes with code snippets if necessary]

### Success Criteria:
**Automated Verification:**
- [ ] Migration applies cleanly: `[command to run migrations]`
- [ ] Unit tests pass: `[command to run tests]`
- [ ] Linter passes: `[command to run linter]`

**Manual Verification:**
- [ ] [Specific, testable action for a human to perform]
- [ ] [Another testable action, perhaps for an edge case]

---

## Phase 2: [Descriptive Name]
*... (repeat structure for all phases)*

---

## 6. Testing Strategy
*An overview of the testing approach, including key scenarios for unit, integration, and end-to-end tests.*

## 7. Migration & Rollback
*If applicable, describe how to handle existing data and the process for rolling back the changes if something goes wrong.*

## 8. References
- Original Ticket: [Link]
- Design Document: [Link]
- Related Research: [Link]
```

## Appendix A: Current XML Files (11)

Location: `src/tunacode/tools/prompts/`

- `bash_prompt.xml`
- `exit_plan_mode_prompt.xml`
- `glob_prompt.xml`
- `grep_prompt.xml`
- `list_dir_prompt.xml`
- `present_plan_prompt.xml`
- `read_file_prompt.xml`
- `run_command_prompt.xml`
- `todo_prompt.xml`
- `update_file_prompt.xml`
- `write_file_prompt.xml`

## Appendix B: Key References

- System prompt: `src/tunacode/prompts/system.md`
- Tool base: `src/tunacode/tools/base.py`
- XML helper: `src/tunacode/tools/xml_helper.py`
- Schema assembler: `src/tunacode/tools/schema_assembler.py`
- Agent registration: `src/tunacode/core/agents/agent_components/agent_config.py` (tools wrapped ~lines 244–266)
- Read-only tool grouping: `src/tunacode/constants.py` (`READ_ONLY_TOOLS`)
