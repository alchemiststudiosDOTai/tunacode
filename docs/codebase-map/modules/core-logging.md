---
title: Core Logging Module
path: src/tunacode/core/logging/
type: module
depth: 1
description: Unified structured logging system with file rotation and TUI output
exports: [LogManager, LogRecord, LogLevel, FileHandler, TUIHandler, get_logger]
seams: [M]
---

# Core Logging Module

## Purpose

Thread-safe structured logging system for TunaCode. Provides semantic log levels for agent operations, file-based persistence with rotation, and optional TUI output during debug mode.

## Key Components

### LogLevel

Enum with standard and semantic levels:

| Level | Value | Purpose |
|-------|-------|---------|
| DEBUG | 10 | Detailed diagnostic info |
| INFO | 20 | General operational messages |
| WARNING | 30 | Potential issues |
| ERROR | 40 | Failures and exceptions |
| THOUGHT | 50 | Agent reasoning (semantic) |
| TOOL | 60 | Tool invocations (semantic) |

### LogRecord

Immutable dataclass containing event metadata:

- **level** - LogLevel enum value
- **message** - Human-readable log message
- **timestamp** - UTC datetime (auto-generated)
- **source** - Module/component name (reserved)
- **request_id** - Session request identifier
- **iteration** - Agent loop iteration number
- **tool_name** - Tool name for TOOL level logs
- **duration_ms** - Timing information
- **extra** - Additional context dict (reserved)

### LogManager

Singleton manager routing records to handlers:

- **get_instance()** - Thread-safe singleton access
- **set_debug_mode(bool)** - Toggle TUI output
- **set_tui_callback(fn)** - Inject TUI write function
- **log(record)** - Route to all handlers
- **log_path** - File log path (active FileHandler target)

Convenience methods: `debug()`, `info()`, `warning()`, `error()`, `thought()`, `tool()`, `lifecycle()`

### Handlers

**FileHandler** - Always active, writes to `~/.local/share/tunacode/logs/tunacode.log`
- 10MB max file size
- 5 backup files (rotation)
- XDG-compliant paths

**TUIHandler** - Active only when debug_mode=True
- Callback-based (no ui layer import)
- Rich Text styling per level

## Usage

```python
from tunacode.core.logging import get_logger

logger = get_logger()
logger.info("Request started", request_id="abc123")
logger.tool("bash", "completed", duration_ms=150.5)
logger.debug("Processing iteration", iteration=i, request_id=ctx.request_id)
logger.lifecycle("Phase 5: dispatching tools", request_id=ctx.request_id, iteration=i)
```

## Log File Format

```
2025-01-10T12:00:00+00:00 [INFO   ] req=abc123 iter=1 Starting agent loop
2025-01-10T12:00:01+00:00 [TOOL   ] req=abc123 iter=1 tool=bash dur=150.0ms completed
```

## Integration Points

- **ui/commands/** - `/debug` command toggles TUI output
- **core/agents/** - Request and iteration logging
- **core/agents/agent_components/** - Tool execution logging

## Seams (M)

**Modification Points:**
- Add new handlers (e.g., remote logging, JSON formatter)
- Extend LogRecord with additional metadata fields
- Add log level filtering per handler
- Implement structured JSON output for log aggregation
