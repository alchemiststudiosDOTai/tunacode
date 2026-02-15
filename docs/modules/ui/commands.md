---
title: UI Command System
summary: Slash commands and shell-command dispatch for the Textual REPL, including the command base contract and tests.
read_when: Adding a new command, changing command parsing, or updating REPL routing behavior.
depends_on: [ui]
feeds_into: [ui]
---

# UI Command System

**Package:** `src/tunacode/ui/commands/`

## What

The REPL delegates user-entered commands through one central router in `tunacode/ui/commands/__init__.py`:

- `!cmd` launches shell commands through `TextualReplApp.start_shell_command()`.
- `/command` routes slash commands via the `COMMANDS` registry.
- `/exit` exits from a slash command; bare `exit` remains supported for backward compatibility.

`handle_command(app, text)` is called from `TextualReplApp.on_editor_submit_requested` before a message is queued for normal agent processing.

## Command contract (base class)

`src/tunacode/ui/commands/base.py`

- `Command` is an abstract base class (`ABC`).
- Required class attributes:
  - `name: str`
  - `description: str`
  - `usage: str = ""` (optional)
- Required method:
  - `execute(self, app: TextualReplApp, args: str) -> Awaitable[None]`

Contract semantics:

- Implementations must be `async` (`inspect.iscoroutinefunction`).
- `args` is the raw string after first whitespace split (`"/cmd arg1 arg2" -> "arg1 arg2"`).
- `app` is expected to be a `TextualReplApp` instance.

## Router behavior

`src/tunacode/ui/commands/__init__.py`

- `COMMANDS: dict[str, Command]` maps slash name to a concrete `Command` instance.
- Current registrations:
  - `help -> HelpCommand`
  - `clear -> ClearCommand`
  - `compact -> CompactCommand`
  - `debug -> DebugCommand`
  - `exit -> ExitCommand`
  - `model -> ModelCommand`
  - `theme -> ThemeCommand`
  - `resume -> ResumeCommand`
  - `update -> UpdateCommand`
`handle_command(app, text)` returns `True` when input is consumed and `False` otherwise.

Routing rules:

- `text.startswith("!")`: strip first char and pass remainder to `app.start_shell_command`.
- `text.startswith("/")`: split into `cmd_name` and `cmd_args` and dispatch `COMMANDS[cmd_name]` if present.
- Unknown slash command: `app.notify("Unknown command: /<name>", severity="warning")`, return `True`.
- `text.lower() == "exit"`: legacy bare `exit` still calls `app.exit()`, return `True`.
- All other input: return `False`.

## Current command implementations

| Command module | Command | Behavior |
|---|---|---|
| `help.py` | `/help` | Renders a command table and writes it to chat (`/help`, `/exit`, `!<cmd>`, `exit`). |
| `exit.py` | `/exit` | Exits the TUI immediately. `exit` is preserved as legacy bare command. |
| `clear.py` | `/clear` | Clears transient runtime artifacts (`thoughts`, `tool_registry`, context state, counters, etc.) and updates UI; conversation history and saved session are preserved for `/resume`. |
| `compact.py` | `/compact` | Compacts history via compaction controller, emits reclamation notice, skips if no old messages. Requires no args. |
| `debug.py` | `/debug` | Toggles `session.debug_mode`; updates logger mode; emits on-screen status. |
| `model.py` | `/model [provider:model-name]` | With arg: validates API key requirements and switches model + persists config. Without arg: opens provider/model picker screens. |
| `theme.py` | `/theme [name]` | With arg: applies known theme and persists config. Without arg: opens picker screen. |
| `resume.py` | `/resume [list|load <id>|delete <id>]` | `list` opens selector, `load` swaps session and replays messages, `delete` removes persisted session file. |
| `update.py` | `/update [check]` | `check` only; default branch runs install flow with confirmation panel, then package upgrade path (`uv` or `pip`). |

Notes:

- `/compact`, `/resume`, and `/update` validate their argument forms and report usage/warnings before mutating state.
- Unknown command and shell invocation failures are surfaced through `TextualReplApp.notify(...)` or shell runner behavior.

## Tests

- `tests/unit/ui/test_command_contracts.py`
  - Discovers concrete `Command` subclasses under `ui/commands/*.py` (excluding `base.py` and `__init__.py`).
  - Asserts each file defines exactly one concrete command subclass.
  - Asserts all discovered commands are present in `COMMANDS` and have non-empty `name`/`description`, valid `execute` coroutine, and `Command` instance.
  - Asserts `COMMANDS` keys match discovered command names.
- `tests/unit/utils/test_shell_command_escape.py`
  - Verifies slash command and shell-command dispatch through `handle_command`, including `/exit`, plus editor bang-mode behavior around `!` toggling.

## Why this shape

A single command registry + `Command` base keeps new command addition low-risk: add a class, wire imports/registration, and the contract test suite enforces coverage automatically.
