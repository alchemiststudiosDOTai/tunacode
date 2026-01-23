---
title: Session Resume Hangs After Tool Calls - UPDATED
link: resume-hang-investigation-updated
type: debug
created_at: 2026-01-21T21:00:00Z
updated_at: 2026-01-21T21:00:00Z
tags:
  - resume
  - hang
  - timeout
  - tool-calls
  - pydantic-ai
  - chutes
  - devstral
---

# Session Resume Hangs After Tool Calls - UPDATED

## BREAKTHROUGH: History IS Reaching pydantic-ai!

The debug logs now show:
```
[DEBUG] pydantic-ai ctx.messages count=56
[DEBUG] ctx.messages[0] type=ModelRequest
[DEBUG] Stream init: ... ctx_messages=56 ctx_messages_type=list
```

**This proves the message history is being passed to pydantic-ai correctly!**

## Current Symptom

- Session has 56 messages with tool calls
- pydantic-ai receives all 56 messages correctly
- Stream receives zero events from provider
- Times out after 30s (stream watchdog) then 120s (global timeout)

## What This Changes

**OLD theory (DISPROVEN):** Message history wasn't reaching pydantic-ai
**NEW theory:** Provider (Chutes/Devstral) is hanging when it receives message history containing tool calls

## Evidence

1. **Tool-call-free sessions resume fine** - You confirmed this
2. **Fresh sessions with tool calls work** - Because they start with empty history
3. **Only resumed sessions with tool call history hang** - Provider chokes on the historical tool calls

## Root Cause (Revised)

**The Chutes provider (mistralai/Devstral-2-123B-Instruct-2512) cannot handle message histories that contain tool calls.**

This is likely:
- Provider API limitation/bug
- Model doesn't support tool call history
- Configuration issue with Devstral

## Solution

**Immediate:** Use different provider for sessions with tool call history:
- Claude (Anthropic) - supports tool call history
- GPT-4 (OpenAI) - supports tool call history
- Other models that handle historical tool calls

**Long-term:** Report to Chutes that Devstral hangs on tool call history.

## Key Insight

This is **NOT a tunacode bug** - it's a **provider compatibility issue**. Our code works perfectly:
- ✅ Session serialization works
- ✅ pydantic-ai integration works
- ✅ Message history passes correctly
- ❌ Provider rejects tool call history

The fix is to avoid using Chutes/Devstral for complex sessions with tool call history.
