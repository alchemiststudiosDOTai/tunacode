---
title: "baseurl Flag and OPENAI_BASE_URL Fix - Beads Plan"
phase: Plan
date: "2025-12-24 21:02:00"
owner: "claude"
parent_research: "memory-bank/research/2025-12-24_20-56-51_baseurl_env_var_fix.md"
git_commit_at_plan: "f5fabc1"
beads_count: 6
tags: [plan, beads, baseurl, cli, config, bug]
---

## Goal

Enable `--baseurl` CLI flag and `OPENAI_BASE_URL` environment variable to work for local vLLM/Ollama/LM Studio connections.

## Scope & Assumptions

### In Scope
- Fixing base_url resolution in `agent_config.py` to check environment and settings
- Adding `OPENAI_BASE_URL` to default user config
- Wiring up the `--baseurl` CLI flag in all entry points

### Out of Scope
- Adding tests (not in scope for this bug fix)
- Documentation updates (handled separately)
- Refactoring provider configuration system (larger effort)

### Assumptions
- Existing Azure `AZURE_OPENAI_ENDPOINT` pattern is the canonical reference
- Setup screen already stores to `settings.base_url` (this is correct)
- Default value for env vars is empty string (existing pattern)

## Deliverables

- Modified `agent_config.py` with cascading base_url fallback
- Updated `defaults.py` with `OPENAI_BASE_URL` in env dict
- Wired `--baseurl` CLI flag in `_default_command`, `main`, subcommand path, and `run_headless`

## Readiness

- Repository at commit `f5fabc1`
- Research document complete with root cause analysis
- Target files identified and patterns documented
- No external dependencies required

## Beads Overview

| ID | Title | Priority | Dependencies | Tags |
|----|-------|----------|--------------|------|
| tunacode-3dt | Add OPENAI_BASE_URL to default env config | P0 | - | config, data, setup |
| tunacode-3qv | Fix base_url resolution in agent_config.py | P0 | - | bug, config, core |
| tunacode-6h9 | Wire --baseurl flag in _default_command | P1 | - | core, ui, cli |
| tunacode-6em | Wire --baseurl flag in deprecated main command | P1 | - | core, ui, cli |
| tunacode-4nf | Wire --baseurl flag for subcommand path | P1 | - | core, ui, cli |
| tunacode-ssk | Wire --baseurl flag in run_headless function | P1 | - | core, ui, cli |

## Dependency Graph

```
tunacode-3dt  (P0) ─────────────────────┐
tunacode-3qv  (P0) ─────────────────────┤
tunacode-6h9  (P1) ─────────────────────┤
tunacode-6em  (P1) ─────────────────────┤
tunacode-4nf  (P1) ─────────────────────┤
tunacode-ssk  (P1) ─────────────────────┘
        │
        └──> All ready, no dependencies
```

All beads are independent and can be executed in any order.

## Bead Details

### tunacode-3dt: Add OPENAI_BASE_URL to default env config

**Priority:** P0
**Dependencies:** None
**Tags:** config, data, setup

## Summary
Add `OPENAI_BASE_URL` to `DEFAULT_USER_CONFIG["env"]` in defaults.py to ensure it is initialized in user config.

## Acceptance Criteria
- [x] `OPENAI_BASE_URL` key added to `DEFAULT_USER_CONFIG["env"]` with empty string default
- [x] Existing env keys (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) remain unchanged
- [x] Code style follows existing patterns

## Files
- `src/tunacode/configuration/defaults.py`

## Notes
This ensures that when user config is created, `OPENAI_BASE_URL` is available in the env dict for resolution by agent_config.py. Empty string is the default value (consistent with other env vars).

---

### tunacode-3qv: Fix base_url resolution in agent_config.py

**Priority:** P0
**Dependencies:** None
**Tags:** bug, config, core

## Summary
Fix base_url resolution at line 294 in agent_config.py to check `env.OPENAI_BASE_URL` and `settings.base_url`, not just the hardcoded `PROVIDER_CONFIG`.

## Acceptance Criteria
- [x] Line 294 now checks `env.get("OPENAI_BASE_URL")` as fallback
- [x] Line 294 now checks `settings.get("base_url")` as final fallback
- [x] Fallback chain: `config.get("base_url") or env.get("OPENAI_BASE_URL") or settings.get("base_url")`
- [x] Azure `AZURE_OPENAI_ENDPOINT` pattern remains unchanged

## Files
- `src/tunacode/core/agents/agent_components/agent_config.py`

## Notes
This fixes the core issue where base_url was only read from PROVIDER_CONFIG and never from environment variables or user settings. The fix mirrors the existing Azure pattern for `AZURE_OPENAI_ENDPOINT` at line 262.

---

### tunacode-6h9: Wire --baseurl flag in _default_command

**Priority:** P1
**Dependencies:** None
**Tags:** core, ui, cli

## Summary
Remove ARG001 marker, rename `_baseurl` to `baseurl`, and wire up the `--baseurl` CLI flag in the `_default_command` function at main.py:85-108. Follow the existing `--model` flag wiring pattern.

## Acceptance Criteria
- [x] `_baseurl` renamed to `baseurl` (no leading underscore)
- [x] ARG001 noqa comment removed
- [x] `baseurl` wired to `state_manager.session.user_config["settings"]["base_url"]` when provided
- [x] Settings dict created if not exists before assignment
- [x] Pattern matches existing `--model` flag wiring

## Files
- `src/tunacode/ui/main.py`

## Notes
The `--model` flag at line 91-92 is wired at line 106-107. Apply same pattern to baseurl. Must ensure settings dict exists before assignment (pattern from setup.py:206-207).

---

### tunacode-6em: Wire --baseurl flag in deprecated main command

**Priority:** P1
**Dependencies:** None
**Tags:** core, ui, cli

## Summary
Remove ARG001 marker, rename `_baseurl` to `baseurl`, and wire up the `--baseurl` CLI flag in the deprecated main command at main.py:113-133. Follow the existing `--model` flag wiring pattern.

## Acceptance Criteria
- [x] `_baseurl` renamed to `baseurl` (no leading underscore)
- [x] ARG001 noqa comment removed
- [x] `baseurl` wired to `state_manager.session.user_config["settings"]["base_url"]` when provided
- [x] Settings dict created if not exists before assignment
- [x] Pattern matches existing `--model` flag wiring

## Files
- `src/tunacode/ui/main.py`

## Notes
The main command is a deprecated alias for tunacode. It must maintain feature parity with `_default_command`. The `--model` flag at line 119-120 is already wired; baseurl must follow same pattern.

---

### tunacode-4nf: Wire --baseurl flag for subcommand path

**Priority:** P1
**Dependencies:** None
**Tags:** core, ui, cli

## Summary
Add `--baseurl` flag wiring in the subcommand invocation path at main.py:103-108 where `ctx.invoked_subcommand` is not None. Follow the existing `--model` flag wiring pattern.

## Acceptance Criteria
- [x] `baseurl` parameter added to `_default_command` function signature (already present as `_baseurl`)
- [x] When `ctx.invoked_subcommand` is not None and baseurl is provided, store to settings
- [x] Settings dict created if not exists before assignment
- [x] Pattern matches existing `--model` flag wiring at line 106-107

## Files
- `src/tunacode/ui/main.py`

## Notes
When subcommands are invoked, CLI flags need to be wired before returning. The `--model` flag has this wiring; `--baseurl` must follow the same pattern. Note: baseurl handling may be combined with bead tunacode-6h9 refactoring.

---

### tunacode-ssk: Wire --baseurl flag in run_headless function

**Priority:** P1
**Dependencies:** None
**Tags:** core, ui, cli

## Summary
Add `--baseurl` parameter to `run_headless` function and wire it to `state_manager.session.user_config["settings"]["base_url"]`. Follow the existing `--model` flag wiring pattern.

## Acceptance Criteria
- [x] `baseurl` parameter added to `run_headless` function signature
- [x] `baseurl` wired to `settings.base_url` when provided
- [x] Settings dict created if not exists before assignment
- [x] Pattern matches existing `--model` flag wiring in `run_headless`

## Files
- `src/tunacode/ui/main.py`

## Notes
Need to locate the `run_headless` function and add baseurl parameter following the same pattern as the model parameter. Must ensure settings dict exists before assignment.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Settings dict may not exist when assigning base_url | Create settings dict if not exists (pattern from setup.py:206-207) |
| Existing users may rely on current behavior | This is a bug fix; behavior change is intentional and expected |
| Multiple beads modifying main.py could conflict | Beads are independent and modify different functions; safe to execute in any order |

## Test Strategy

Each bead has a single acceptance test focused on the specific change:
- `tunacode-3dt`: Verify `OPENAI_BASE_URL` in defaults
- `tunacode-3qv`: Verify fallback chain in agent_config.py
- `tunacode-6h9`, `tunacode-6em`, `tunacode-4nf`, `tunacode-ssk`: Verify flag is wired to settings

## References

- Research: `memory-bank/research/2025-12-24_20-56-51_baseurl_env_var_fix.md`
- `agent_config.py:294` - Target line for base_url fix
- `agent_config.py:262` - Azure pattern reference
- `main.py:88-89`, `main.py:116-117` - Dead code locations
- `setup.py:205-208` - Settings dict creation pattern
- `defaults.py:11-29` - Default config structure

## Ready Queue

```
All beads completed (6/6).
```

## Final Gate

- Plan path: `memory-bank/plan/2025-12-24_21-02-00_baseurl-env-var-fix-beads.md`
- Beads created: 6
- Ready for execution: 6
- Next command: `/context-engineer:execute-beads`
