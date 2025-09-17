---
title: "ReAct Loop Agent MVP – Plan"
phase: Plan
date: "2025-09-17 17:15:00"
owner: "context-engineer:plan"
parent_research: "memory-bank/research/2025-09-17_17-14-35_react_loop_agent_research.md"
git_commit_at_plan: "f6f71e8"
tags: [plan, react-agent, mvp]
---

## Goal
Implement a minimal ReAct loop agent with manager-worker execution using ~100 lines of code by extending existing patterns.

## Deliverables
1. ReAct agent factory (20 lines)
2. Manager agent factory (15 lines)
3. Simple orchestrator (30 lines)
4. Basic ReAct prompt template

## Work Breakdown

### Task 1: Add ReAct support to agent_config.py
- Extend existing `get_or_create_agent()` with mode parameter
- Add ReAct prompt tail
- Use existing caching pattern

### Task 2: Create orchestrator function
- Manager agent breaks task into 2-3 workers
- Workers execute in parallel using `asyncio.gather()`
- Simple budget: max 5 turns per worker

### Task 3: Add ReAct mode to main.py
- New `process_react_request()` function
- Reuse existing tool execution
- Minimal state tracking

## Success Criteria
- ReAct agents run with Thought→Action→Observation pattern
- Manager creates parallel workers
- Workers respect turn limits
- <100 lines of new code
