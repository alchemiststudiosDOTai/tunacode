---
allowed-tools: Bash(*), Edit(*), Read(*), View(*)
description: Drive one task end-to-end using Task Master with scratchpad.sh for planning and notes
---

# /tm/work — Task Master Workflow with Scratchpad

Execute a complete task workflow using **Task Master** for task management and `scratchpad.sh` for planning, notes, and context tracking.

## Arguments
**$ARGUMENTS** = Task ID(s) (comma-separated), empty (auto-select next), or free-text description (create new task)

## Pre-flight Checklist
```bash
# Verify Task Master availability
!which task-master || echo "Task Master not found. Install via: npm install -g task-master-ai"

# Verify scratchpad.sh exists and is executable
!test -x ./scratchpad.sh || echo "scratchpad.sh not found or not executable. Run: chmod +x ./scratchpad.sh"

# Check current date/time for context
!date "+%Y-%m-%d %H:%M:%S"

# Verify project initialization
!test -d .taskmaster || echo "Project not initialized. Run: task-master init"
```

## Phase 1: Task Resolution & Context Gathering

### A) Numeric Task IDs Provided
```bash
# Show specified tasks
!task-master show $ARGUMENTS

# Create initial scratchpad entry
!./scratchpad.sh "## Task Work Session: $(date '+%Y-%m-%d %H:%M')\n### Working on Task(s): $ARGUMENTS"

# Get task details and dependencies
!task-master show $ARGUMENTS --detailed
!task-master analyze-dependencies $ARGUMENTS
```

### B) Empty Arguments (Auto-select Next)
```bash
# Get next recommended task
NEXT_TASK=$(!task-master next --format=id)

# Show task details
!task-master show $NEXT_TASK

# Initialize scratchpad
!./scratchpad.sh "## Task Work Session: $(date '+%Y-%m-%d %H:%M')\n### Auto-selected Task: $NEXT_TASK"

# Analyze complexity
!task-master analyze-complexity $NEXT_TASK
```

### C) Free-text Description (Create New)
```bash
# Create new task from description
NEW_TASK_ID=$(!task-master create "$ARGUMENTS" --output=id)

# Show created task
!task-master show $NEW_TASK_ID

# Document in scratchpad
!./scratchpad.sh "## Task Work Session: $(date '+%Y-%m-%d %H:%M')\n### Created Task: $NEW_TASK_ID\nDescription: $ARGUMENTS"
```

## Phase 2: Task Analysis & Planning

### Step 1: Comprehensive Context Analysis
```bash
# Analyze task complexity and requirements
!task-master analyze-complexity $TASK_ID

# Check dependencies
!task-master list-dependencies $TASK_ID

# Review related files
!task-master show $TASK_ID --files

# Document findings in scratchpad
!./scratchpad.sh "\n## Task Analysis for #$TASK_ID\n\n### Complexity Score\n$(!task-master analyze-complexity $TASK_ID)\n\n### Dependencies\n$(!task-master list-dependencies $TASK_ID)"
```

### Step 2: Planning Documentation
Create structured plan in scratchpad:
```bash
!./scratchpad.sh "\n## Implementation Plan\n\n### Approach\n- [ ] Step 1: ...\n- [ ] Step 2: ...\n- [ ] Step 3: ...\n\n### Technical Decisions\n- Architecture: ...\n- Key libraries: ...\n- Testing strategy: ...\n\n### Success Criteria\n- [ ] All tests pass\n- [ ] Code review complete\n- [ ] Documentation updated"
```

### Step 3: Environment Preparation
```bash
# Check branch status
!git status --short

# Create feature branch if needed
!git checkout -b "task-$TASK_ID" 2>/dev/null || echo "Branch exists"

# Document branch info
!./scratchpad.sh "\n### Git Context\nBranch: $(git branch --show-current)\nStatus: Clean workspace"
```

## Phase 3: Implementation Workflow

### Step 1: Task Initiation
```bash
# Start task formally
!task-master start $TASK_ID

# Generate implementation files if applicable
!task-master generate $TASK_ID

# Update scratchpad with start time
!./scratchpad.sh "\n## Implementation Started: $(date '+%H:%M:%S')"
```

### Step 2: Active Development Loop
Implement iterative development with continuous note-taking:

```bash
# After each significant change, update notes
!./scratchpad.sh "\n### Progress Update $(date '+%H:%M')\n- Completed: [specific achievement]\n- Next: [immediate next step]\n- Blockers: [any issues]"

# Periodically check task status
!task-master status $TASK_ID

# Run tests frequently
!npm test 2>&1 | tee -a test-results.log
!./scratchpad.sh "\n### Test Run $(date '+%H:%M')\nResult: $(tail -1 test-results.log)"
```

### Step 3: Code Quality Checks
```bash
# Linting
!npm run lint 2>&1 | tee lint-results.log

# Type checking (if applicable)
!npm run type-check 2>&1 | tee type-results.log

# Document results
!./scratchpad.sh "\n### Quality Checks\n- Lint: $(grep -c 'error' lint-results.log) errors\n- Types: $(grep -c 'error' type-results.log) errors"
```

## Phase 4: Testing & Validation

### Step 1: Comprehensive Testing
```bash
# Run full test suite
!npm test -- --coverage

# Run integration tests if separate
!npm run test:integration

# Performance benchmarks if applicable
!npm run test:performance

# Update scratchpad with results
!./scratchpad.sh "\n## Test Results\n- Unit: $(npm test -- --coverage | grep 'All files' | awk '{print $10}')\n- Integration: Pass/Fail\n- Performance: Metrics"
```

### Step 2: Manual Verification
Document manual testing in scratchpad:
```bash
!./scratchpad.sh "\n### Manual Testing Checklist\n- [ ] Feature works as expected\n- [ ] Edge cases handled\n- [ ] UI/UX acceptable\n- [ ] No console errors\n- [ ] Accessibility verified"
```

## Phase 5: Documentation & Review

### Step 1: Update Documentation
```bash
# Check what docs need updating
!grep -r "TODO\|FIXME\|XXX" docs/ README.md

# Document changes made
!./scratchpad.sh "\n## Documentation Updates\n- [ ] README.md updated\n- [ ] API docs updated\n- [ ] Changelog entry added\n- [ ] Migration guide (if needed)"
```

### Step 2: Self-Review Checklist
```bash
# Generate diff summary
!git diff --stat

# Create review checklist in scratchpad
!./scratchpad.sh "\n## Pre-Completion Review\n- [ ] Code follows project standards\n- [ ] No debug code left\n- [ ] Error handling complete\n- [ ] Performance acceptable\n- [ ] Security considerations addressed"
```

## Phase 6: Task Completion

### Step 1: Finalize Implementation
```bash
# Stage all changes
!git add -A

# Create detailed commit
!git commit -m "feat: Complete task #$TASK_ID

$(./scratchpad.sh | grep -A5 'Implementation Plan' | grep '\[x\]')"

# Push branch
!git push origin "task-$TASK_ID"
```

### Step 2: Mark Task Complete
```bash
# Complete the task in Task Master
!task-master complete $TASK_ID

# Add completion notes
!task-master add-note $TASK_ID "Completed implementation. See branch task-$TASK_ID"

# Final scratchpad entry
!./scratchpad.sh "\n## Task Completed: $(date '+%Y-%m-%d %H:%M:%S')\n\n### Summary\n- Time spent: [calculate]\n- Lines changed: $(git diff --stat | tail -1)\n- Tests added: [count]\n\n### Lessons Learned\n- [Key insight 1]\n- [Key insight 2]"
```

### Step 3: Archive Session Notes
```bash
# Create permanent record
!mkdir -p .taskmaster/completed-tasks/
!cp scratchpad.md ".taskmaster/completed-tasks/task-$TASK_ID-$(date +%Y%m%d).md"

# Clear scratchpad for next session (optional)
!./scratchpad.sh --archive
```

## Phase 7: Post-Task Workflow

### Step 1: Update Task Board
```bash
# Show updated task list
!task-master list --status=all

# Check for newly unblocked tasks
!task-master next --show-reasons
```

### Step 2: Knowledge Transfer
```bash
# If task revealed important patterns, document them in
.claude/
├── metadata/       # Component information
├── code_index/     # Code relationships
├── debug_history/  # Debugging sessions
├── patterns/       # Implementation patterns
├── cheatsheets/    # Quick references
├── qa/            # Questions & answers
├── delta/         # Change logs
├── anchors/       # Important locations

if these dirs dont exist create them

you MUST title the document a clear title and dated with a DATE
```

## Error Handling

### Common Issues & Recovery
```bash
# If Task Master fails
if ! task-master status; then
    echo "Task Master error. Attempting to recover..."
    # Save current work
    !git stash push -m "WIP: Task $TASK_ID"
    # Document issue
    !./scratchpad.sh "\n## ERROR: Task Master failure at $(date)\nRecovery: Work stashed"
fi

# If tests fail repeatedly
if [ $TEST_FAILURES -gt 3 ]; then
    !./scratchpad.sh "\n## BLOCKED: Persistent test failures\nNext steps:\n1. Review test output\n2. Check with team\n3. Consider task decomposition"
    !task-master add-note $TASK_ID "Blocked: test failures"
fi
```

## Success Criteria
- ✅ Task moved from "todo" to "done" status
- ✅ All code changes committed and pushed
- ✅ Tests passing with >90% coverage
- ✅ Documentation updated
- ✅ Scratchpad notes archived
- ✅ No linting errors
- ✅ Performance benchmarks met (if applicable)
- ✅ Security scan passed (if applicable)

## Usage Examples

### Example 1: Work on specific task
```bash
/tm/work 42
```

### Example 2: Auto-select next task
```bash
/tm/work
```

### Example 3: Create and work on new task
```bash
/tm/work "Implement user authentication with JWT"
```

### Example 4: Work on multiple related tasks
```bash
/tm/work 42,43,44
```
