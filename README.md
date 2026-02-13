# tunacode-cli

<img src="docs/images/tunacode.png" alt="tunacode" width="600"/>

[![PyPI version](https://badge.fury.io/py/tunacode-cli.svg)](https://badge.fury.io/py/tunacode-cli)
[![Downloads](https://pepy.tech/badge/tunacode-cli)](https://pepy.tech/project/tunacode-cli)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord Shield](https://discord.com/api/guilds/1447688577126367346/widget.png?style=shield)](https://discord.gg/TN7Fpynv6H)

A terminal-based AI coding agent with a NeXTSTEP-inspired interface.

> **Note:** Under active development - expect bugs.

## Features

- **Any model** - Works with any OpenAI-compatible API (Anthropic, OpenAI, Google, Ollama, vLLM, etc.)
- **File operations** - Read, write, update files with fuzzy matching for edits
- **Shell access** - Run bash commands with output capture
- **Code search** - Glob patterns and grep with ripgrep integration
- **Session persistence** - Resume previous conversations with `/resume`
- **LSP diagnostics** - Real-time code errors after file writes (Python, TypeScript, Go, Rust)
- **Themeable UI** - CSS-based theming with NeXTSTEP-inspired design
- **Copy-on-select** - Automatically copies highlighted text to clipboard
- **Agent loop** - Powered by [tinyagent](https://github.com/alchemiststudios.ai/tinyAgent)

## Interface

![Agent Response Panel](docs/media/agent-response.png)
*Agent response with NeXTSTEP-style panels*

![Read File Tool](docs/media/read-file-tool.png)
*Tool output with syntax highlighting*

## Architecture

TunaCode is built with:

- **tinyagent** - Core agent loop handling LLM interaction and tool execution
- **Textual** - Terminal UI framework with CSS-based styling
- **Rich** - Terminal rendering with syntax highlighting
- **Typer** - CLI framework

The agent system uses typed cache accessors with pluggable invalidation strategies (manual and mtime-based).

### Migration Notes

**Recent Breaking Changes:**

- Session persistence format changed - existing sessions may not load correctly
- Tool execution is now sequential (was parallel)
- The `docs/` directory has been restructured

For full details, see the [CHANGELOG](CHANGELOG.md).

## Installation

### End Users

```bash
uv tool install tunacode-cli
```

Or with pip:
```bash
pip install tunacode-cli
```

### Developers (Fresh Clone)

```bash
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode
make dev-setup
```

Or without make:
```bash
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode
./scripts/dev-setup.sh
```

## Development

Common development tasks:

```bash
make dev-setup  # Full setup for fresh clone
make install    # Install/update dependencies
make run        # Run the development server
make test       # Run test suite
make lint       # Run linters
make clean      # Clean build artifacts
```

View technical debt:

```bash
uv run python scripts/todo_scanner.py --format text
```

## Quick Start

```bash
# Configure API key
tunacode --setup

# Start coding
tunacode
```

## Configuration

Set your API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-key"
# or
export OPENAI_API_KEY="your-key"
```

Config file: `~/.config/tunacode.json`

For local models and advanced settings, see the [Configuration Guide](docs/configuration/README.md).

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model` | Change AI model |
| `/clear` | Clear UI state (messages preserved) |
| `/theme` | Change UI theme |
| `/resume` | Load previous sessions |
| `/update` | Check for updates |
| `!<cmd>` | Run shell command |
| `exit` | Quit |

## Tools

The agent has access to:

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line ranges |
| `write_file` | Create new files |
| `update_file` | Edit existing files with fuzzy matching |
| `bash` | Execute shell commands |
| `glob` | Find files by pattern |
| `grep` | Search file contents |
| `list_dir` | List directory tree |
| `web_fetch` | Fetch web page content |

## LSP Integration

Automatic code diagnostics when LSP servers are in PATH:

| Language | Server |
|----------|--------|
| Python | `ruff server` |
| TypeScript/JS | `typescript-language-server` |
| Go | `gopls` |
| Rust | `rust-analyzer` |

## Security

TunaCode has **full shell access** with no permission prompts. If you're concerned:
- Use git so you can revert changes
- Run in a container/sandbox

## Discord

[<img src="https://discord.com/api/guilds/1447688577126367346/widget.png?style=banner3" alt="Discord"/>](https://discord.gg/TN7Fpynv6H)

## License

MIT
