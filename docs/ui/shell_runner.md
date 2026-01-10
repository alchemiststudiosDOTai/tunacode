# Shell Runner

**Date:** 2026-01-10
**Scope:** UI / Shell
**Status:** Canonical

## Overview

The Shell Runner provides inline shell command execution via the `!` prefix. Commands execute asynchronously and output renders as 4-zone NeXTSTEP panels, matching the agent's bash tool format.

**Location:** `src/tunacode/ui/shell_runner.py`

## Usage

```
! ls -la          # Execute shell command
! git status      # Any valid shell command
!                 # Toggle bash mode (empty)
```

Press `!` in empty editor to toggle bash mode. Press `Esc` to cancel running command.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Editor    │────▶│ ShellRunner  │────▶│ BashRenderer │
│  (! prefix) │     │  (async)     │     │  (4-zone)    │
└─────────────┘     └──────────────┘     └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ ShellRunner  │
                    │    Host      │
                    │  (protocol)  │
                    └──────────────┘
```

### ShellRunnerHost Protocol

The runner communicates with the UI via a protocol:

```python
class ShellRunnerHost(Protocol):
    def notify(self, message: str, severity: str = "information") -> None: ...
    def write_shell_output(self, renderable: RenderableType) -> None: ...
    def shell_status_running(self) -> None: ...
    def shell_status_last(self) -> None: ...
```

### Output Format

Shell output is formatted as 4-zone NeXTSTEP panels via `BashRenderer`:

```
┌──────────────────────────────────────────────────┐
│ [bold]bash[/]   ✓ exit 0                         │  Zone 1: Command + exit
│ cwd: /home/user/project   timeout: 30s           │  Zone 2: Working dir
│ ──────────                                       │  Separator
│ file1.py                                         │  Zone 3: stdout/stderr
│ file2.py                                         │
│ ──────────                                       │  Separator
│ 2 lines  stdout                        145ms     │  Zone 4: Stats
└──────────────────────────────────────────────────┘
```

## Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `SHELL_COMMAND_TIMEOUT_SECONDS` | 30.0 | Max execution time |
| `SHELL_COMMAND_CANCEL_GRACE_SECONDS` | 0.5 | Grace period before SIGKILL |
| `SHELL_OUTPUT_ENCODING` | utf-8 | Output decoding |
| `SHELL_CANCEL_SIGNAL` | SIGINT | Cancellation signal |

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Empty command | Shows usage text, no task started |
| Already running | Warning notification, blocks second start |
| Timeout (30s) | Process killed, error notification |
| Cancellation | SIGINT → grace period → SIGKILL |
| Non-zero exit | Panel rendered + warning notification |
| Exception | Panel with `"(shell error)"` placeholder (Issue #225) |

## Testing

Tests in `tests/test_shell_runner.py` use `MockHost` implementing the protocol:

```python
@dataclass
class MockHost(ShellRunnerHost):
    notifications: list[tuple[str, str]] = field(default_factory=list)
    outputs: list[RenderableType] = field(default_factory=list)
    # ...
```

### Test Coverage

- `test_empty_command_shows_usage` - Empty string validation
- `test_whitespace_only_command_shows_usage` - Whitespace trimming
- `test_already_running_blocks_second_start` - Concurrency guard

## Known Issues

**Issue #225:** Exception handler in `_on_done` loses original command context, replacing with `"(shell error)"` placeholder. The command should be preserved for debugging.

## Related

- [Tool Renderers](tool_renderers.md) - 4-zone panel architecture
- [Design Philosophy](design_philosophy.md) - NeXTSTEP principles
- `src/tunacode/ui/renderers/tools/bash.py` - BashRenderer implementation
