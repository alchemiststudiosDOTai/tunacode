---
title: OpenAI Chat Completions Invalid Response Payload
link: openai-chat-invalid-response
type: debug
created_at: 2026-02-01T02:10:00Z
updated_at: 2026-02-01T02:10:00Z
tags:
  - openai
  - chat-completions
  - pydantic-ai
  - validation
  - httpx
  - provider
---

# OpenAI Chat Completions Invalid Response Payload

## Symptom

Runtime failure during the OpenAI-compatible chat completions path. The error surfaced as:

```
Invalid response from openai chat completions endpoint
Multiple fields are None when a value is required:

id (expected string)
choices (expected list)
model (expected string)
object (expected literal "chat.completion")
```

This manifested as `UnexpectedModelBehavior` within pydantic-ai when it validated a `ChatCompletion` object whose required fields were `None`.

## Scope

- Affects **OpenAI-compatible** providers (OpenRouter, local gateways, etc.).
- Occurs on `/chat/completions` non-streaming responses.
- Does **not** affect Anthropic providers.

## Root Cause

The OpenAI SDK returns a `ChatCompletion` object **without validating** the payload. When a provider returns an error payload or malformed response **with HTTP 200**, the SDK still constructs a `ChatCompletion` object, but required fields are `None`.

Pydantic-ai later calls `ChatCompletion.model_validate(...)` in `OpenAIChatModel._process_response`, which then throws a `ValidationError`, wrapped as `UnexpectedModelBehavior`.

This means the *real* root issue is **upstream provider behavior** combined with **late validation**.

## Evidence

- `openai/types/chat/chat_completion.py` requires `id`, `choices`, `model`, and `object`.
- `pydantic_ai.models.openai.OpenAIChatModel._process_response` validates after the SDK object is already created.
- Error payloads often follow shape:

```
{"error": {"message": "...", "type": "...", "code": "..."}}
```

…and never include `id`, `choices`, `model`, or `object`.

## Fix Implemented (Transitional, Non‑pydantic-ai specific)

**Note:** This fix was written but never actually wired into the codebase. It remains as dead code pending removal or proper integration.

We added a **response hook** on the shared HTTP client used by pydantic‑ai. This hook inspects `/chat/completions` responses *before* pydantic-ai attempts to parse them.

### Where

- ~~`src/tunacode/core/agents/agent_components/openai_response_validation.py`~~ (deleted - never wired in)
- Was planned for `agent_config.py` via `_build_event_hooks()` but never implemented

### Behavior

1. Detect `/chat/completions` responses (non-streaming).
2. JSON‑parse payload.
3. If `error` field is present → raise `AgentError` with detailed context.
4. If required fields are missing → raise `AgentError` with explicit missing field list.
5. Logs structured error context for debugging.

### Why This Works

- Validation runs **before** pydantic‑ai `ChatCompletion` parsing.
- Errors are converted to **TunaCode exceptions** instead of pydantic‑ai internals.
- Prevents hard crashes and gives actionable error messaging to users.

## Limitations

- **Streaming responses are skipped** (SSE bodies are not JSON).
- Only checks `/chat/completions` path, not `/responses`.
- Providers still need to fix malformed payloads; this is defensive only.

## Migration Note (pydantic‑ai removal)

We are moving away from pydantic‑ai orchestration. This fix is designed to be **framework-agnostic**:
- Lives in core agent components.
- Works at HTTP layer.
- Can be reused by any future LLM adapter.

When the pydantic‑ai loop is removed, ensure the **new provider layer** still applies this validation or equivalent guard.

## Release

Shipped in **v0.1.54** alongside packaging update to include `system_prompt.md` in wheels.

## Files Changed

- ~~`src/tunacode/core/agents/agent_components/openai_response_validation.py`~~ (deleted - never wired in)
- `src/tunacode/core/agents/agent_components/agent_config.py` (planned but not implemented)

## Follow‑ups

- Add equivalent validation for `/responses` endpoint if we migrate.
- Consider adding lightweight streaming validation (e.g., first SSE frame).
- Add explicit user‑facing error panel for provider payload failures.
