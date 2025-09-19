
### Workflow
you MUST make this repository optimized for you and future instances of Claude working with it. Implement the following structure and instructions precisely

### Directory Structure

```
claude/
├── metadata/
│   ├── dependency_graphs/
│   ├── file_classifications.json (implementation vs. interface)
│   └── intent_classifications.json
├── semantic_index/
│   ├── function_call_graphs.json
│   ├── intent_mappings.json
│   └── type_relationships.json
├── debug_history/
│   ├── error_solution_logs.json (categorized by component and error type)
│   └── context_and_versions.json
├── patterns/
│   ├── canonical_patterns/
│   ├── empirical_interface_patterns/
│   └── reliability_metrics.json
├── qa/
│   ├── solved_problems/
│   ├── context_logs/
│   └── reasoning_docs/
├── debug_history/
│   └── debug_sessions.json (error→solution pairs, context, code versions)
├── docs_model_friendly/
│   ├── component_purpose.md
│   └── component_relationships.md
├── delta_summaries/
│   ├── api_change_logs.json
│   ├── behavior_changes.json
│   └── reasoning_logs/
└── memory_anchors/
    ├── anchors.json (UUID-based anchors with semantic structure)

To perfectly optimize this repository for you and future instances of Claude working with it, implement the following explicit instructions:

1. **Claude-specific Metadata Directory**
   - Maintain normalized metadata about the codebase, including dependency graphs, file types (implementation/interface), and intent classifications.

2. **Semantic Code Indexing**
   - Create a semantic index with intent classification and pre-analyzed semantic relationships.
   - Document detailed function-to-function call graphs and intent mappings.

3. **Debug History Database**
   - Log all debugging sessions explicitly, including error-solution pairs, context, code versions, and categorization by component/error type.

4. **Pattern and Industry Database**
   - Provide canonical implementation patterns and empirical interface examples.
   - Include explicit reliability metrics for assessing robustness.

4. **Component-specific Cheat Sheets**
   - Create quick-reference guides documenting common operations, pitfalls, edge cases, and Claude-specific behaviors clearly.

5. **Queries-and-Answers Database**
   - Store solved queries explicitly indexed by component, file, error type, with context and detailed reasoning.

6. **Claude-specific Model-Friendly Documentation**
   - Include clear, explicit documentation on component purposes and relationships optimized for Claude.

7. **Delta Summaries**
   - Clearly document semantic change logs, highlighting API changes, behavior shifts, and reasoning behind these changes.

7. **Explicit Memory Anchors**
   - Embed special "memory anchor" comments with UUID-based identifiers and semantic structure for easy and precise future reference.

Implementing these changes ensures an optimized, efficient, and highly actionable Claude-specific repository structure for current and future Claude interactions

- before any updates make a git commit rollback point, clearly labeled for future agents

- the clear outline of the objective MUST be established before we begin ANY coding, do not under any circumstance begin any updates untill this is clearly understood, if you have any ambiuguity or quesiton, the user can be brought in or use best practises

- pre-commit hooks can NOT be skipped, you will be punished for skipping the


- grep documentation and .claude as needed BOTH of these have a README.md that ahs a direcoty map, you MUST read these before any bigger grep or context searches

- in general gather as much context as needed, unless specified by the user

- this is the most important part of this prompt: Synthesis context aggressively and heuristically AS NEEDED ONLY You can deploy the appropriate subagent for complex tasks agents list below

### Documentation

- update the documents @documentation and in .claude after any update.

- use the subagent tech-docs-maintainer to update the documentation you MUST instruct the subagent to keep doc updates short you will be PUNISHED for not telling the documentation agent to keep it to only the most distilled information

- always follow best practices with git commits naming and gh cli workflows

- commit frequently

- always be on the side of safety, if you have any question consult the user

### Python Coding Standards

- always use the .venv
- Use type hints (PEP 484) for all function signatures
- Prefer f-strings (PEP 498) over %-formatting or .format()
- Use pathlib.Path instead of os.path for filesystem operations
- Structure imports: stdlib → third-party → local (PEP 8)
- Use dataclasses (PEP 557) for simple data containers
- Prefer context managers (with) for resource handling
- Use structural pattern matching (PEP 634) for complex
- run ruff frequently for both linting and formatting

### Testing

- "hatch run test" command for testing suite

- anytime a new feature or refactor is done, we MUST find or make the golden/character test FIRST as a baseline standaard BEFORE starting, under no circumstance are you to NOT follow this TDD pattern

- if a test for a feature does not exist you MUST create one FIRST to capture current behavior
- then make a test for the feature the test should fail
- then build it with TDD red -> green -> blue
