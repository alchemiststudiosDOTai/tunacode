---
title: "Tokens/Second Display – Plan"
phase: Plan
date: "2026-01-24 12:15:00"
owner: "tuna"
parent_research: "memory-bank/research/2026-01-24_11-47-37_tokens-per-second-display.md"
git_commit_at_plan: "b3829ebd"
tags: [plan, tokens-per-second, ui, coding]
---

## Goal

Show t/s in the agent panel status bar.

## The Change

**File:** `src/tunacode/ui/renderers/agent_response.py`

**Location:** Line 195, after the model check, before the tokens check

**Add this line:**
```python
status_parts.append(f"{tokens * 1000 / duration_ms:.0f} t/s")
```

**Result:** `"ANTH/claude-sonnet-4-5  ·  343 t/s  ·  1.2k  ·  3.5s"`

## Done

That's it. One line. We have the data, we format it.
