# Architect Mode Refactor Plan

This document outlines the planned refactor of the `/architect` mode to an adaptive ReAct based approach.

## Problem

* The previous architect mode generated an entire plan up‑front and executed it blindly.
* There was no feedback loop between steps which meant a failing task could not be corrected.
* Behaviour diverged from the core agent making maintenance difficult.

## Solution Overview

1. **Update Planner Schema** – Each task now contains a `tool` and `args` field so the planner returns executable steps.
2. **ReAct Agent** – New `ReActAgent` manages planning and step‑wise execution while capturing observations.
3. **Tool Handler** – Centralised dispatch that invokes the correct tool based on a task's `tool` field.
4. **Orchestrator Update** – Simplified orchestrator that delegates to `ReActAgent` for running requests.
5. **Prompt Refinement** – The architect planner prompt instructs the LLM to use the updated schema with tool and args.

## File Changes

- `src/tunacode/core/agents/planner_schema.py` – Added `tool` and `args` fields to `Task`.
- `src/tunacode/core/agents/react_agent.py` – New adaptive ReAct implementation.
- `src/tunacode/core/tool_handler.py` – Executes tools referenced in a task.
- `src/tunacode/core/agents/orchestrator.py` – Delegates execution to `ReActAgent`.
- `src/tunacode/prompts/architect_planner.md` – Prompt updated to require new fields.

## Technical Flow

1. User request enters `/architect` mode via `OrchestratorAgent`.
2. `OrchestratorAgent` invokes `ReActAgent` which calls the planner LLM.
3. Planner returns a `Plan` composed of `Task` objects (with tool and args).
4. `ReActAgent` iterates through tasks and sends each to `ToolHandler`.
5. `ToolHandler` calls the correct tool function (`read_file`, `grep`, `update_file`, etc.) and returns the observation.
6. Results from all steps are collected and returned to the user.

## Testing Guide

1. Unit tests for `ReActAgent` verifying the plan/execute loop and state handling.
2. Unit tests for `ToolHandler` ensuring each tool dispatches correctly.
3. Integration tests invoking the `/architect` command to validate end‑to‑end behaviour.
4. Edge case tests covering failing steps and empty plans to confirm graceful failure modes.
