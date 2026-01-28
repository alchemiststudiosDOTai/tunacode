# Research – Kimi For Coding API Headers

**Date:** 2026-01-28
**Owner:** Claude
**Phase:** Research

## Goal

Document what headers tunacode sends to LLM API providers, so the Kimi team can whitelist tunacode for "Kimi For Coding" access.

## Findings

### Current HTTP Client Configuration

**File:** `src/tunacode/core/agents/agent_components/agent_config.py:402-404`

```python
http_client = AsyncClient(
    transport=transport,
    event_hooks=event_hooks,
    timeout=http_timeout
)
```

**No custom headers are configured.** The HTTP client uses httpx defaults.

### Headers Currently Sent to LLM Providers

| Header | Value | Source |
|--------|-------|--------|
| User-Agent | `python-httpx/<version>` | httpx default |
| Authorization | `Bearer <api_key>` | pydantic-ai provider |
| Content-Type | `application/json` | pydantic-ai provider |

### Version Information Available

**File:** `src/tunacode/constants.py:19-20`
```python
APP_NAME = "TunaCode"
APP_VERSION = "0.1.49"
```

**Package name:** `tunacode-cli` (PyPI)
**Website:** https://tunacode.xyz

### Web Fetch Tool (Separate from LLM API)

**File:** `src/tunacode/tools/web_fetch.py:27`
```python
USER_AGENT = "TunaCode/1.0 (https://tunacode.xyz)"
```

This is used only for web browsing, NOT for LLM API calls.

## Implementation Path

To add custom headers for Kimi whitelisting, modify `agent_config.py:402`:

```python
from tunacode.constants import APP_NAME, APP_VERSION

user_agent = f"{APP_NAME}/{APP_VERSION} (https://tunacode.xyz; python-httpx)"

http_client = AsyncClient(
    transport=transport,
    event_hooks=event_hooks,
    timeout=http_timeout,
    headers={
        "User-Agent": user_agent,
        # Optional additional headers if Kimi requires:
        "X-Client-Name": APP_NAME,
        "X-Client-Version": APP_VERSION,
    }
)
```

## Questions for Kimi Team

1. What header(s) does Kimi check for whitelisting coding agents?
2. Is `User-Agent` containing "TunaCode" sufficient?
3. Do they need a specific header format or value?
4. Is there a registration/approval process?

## Key Files

- `src/tunacode/core/agents/agent_components/agent_config.py` → HTTP client creation
- `src/tunacode/constants.py` → Version constants
- `src/tunacode/tools/web_fetch.py` → Example of custom User-Agent

## References

- Error message: "Kimi For Coding is currently only available for Coding Agents such as Kimi CLI, Claude Code, Roo Code, Kilo Code, etc."
- Error type: `access_terminated_error`
