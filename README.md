# tunacode-cli

<img src="docs/images/logo.jpeg" alt="tunacode logo" width="200"/>

[![PyPI version](https://badge.fury.io/py/tunacode-cli.svg)](https://badge.fury.io/py/tunacode-cli)
[![Downloads](https://pepy.tech/badge/tunacode-cli)](https://pepy.tech/project/tunacode-cli)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord Shield](https://discord.com/api/guilds/1447688577126367346/widget.png?style=shield)](https://discord.gg/TN7Fpynv6H)

A TUI code agent.

> **Note:** Under active development - expect bugs.



## Interface

The Textual-based terminal user interface provides a clean, interactive environment for AI-assisted coding, with a design heavily inspired by the classic NeXTSTEP user interface.

![Agent Response Panel](docs/media/agent-response.png)
*Agent response panel with formatted output*

![Read File Tool](docs/media/read-file-tool.png)
*Tool rendering with syntax highlighting*

![Plan Approval](docs/media/plan-approval.png)
*Structured plan approval workflow*

## Theme Support

The interface supports multiple themes for different preferences and environments.

Customize the appearance with built-in themes or create your own color schemes.

## Model Setup

Configure your AI models and settings through the provided setup interface.

**Note:** TunaCode has full bash shell access. This tool assumes you know what you're doing. If you're concerned, run it in a sandboxed environment.

## v0.1.1 - Major Rewrite

This release is a complete rewrite with a new Textual-based TUI.

**Upgrading from v1?** The legacy v1 codebase is preserved in the `legacy-v1` branch and will only receive security updates.

## Requirements

- Python 3.11+

## Installation

```bash
uv tool install tunacode-cli
```

## Quick Start

1. Run the setup wizard to configure your API key:

```bash
tunacode --setup
```

2. Start coding:

```bash
tunacode
```

## Configuration

Set your API key as an environment variable or use the setup wizard:

```bash
export OPENAI_API_KEY="your-key"
# or
export ANTHROPIC_API_KEY="your-key"
```

Config file location: `~/.config/tunacode.json`

For advanced settings including **local mode** for small context models, see the [Configuration Guide](docs/configuration/README.md).

## Commands

| Command  | Description                  |
| -------- | ---------------------------- |
| /help    | Show available commands      |
| /model   | Change AI model              |
| /clear   | Clear conversation history   |
| /yolo    | Toggle auto-confirm mode     |
| /branch  | Create and switch git branch |
| /plan    | Toggle read-only planning    |
| /theme   | Change UI theme              |
| /resume  | Load/delete saved sessions   |
| !<cmd>   | Run shell command            |
| exit     | Quit tunacode                |

## LSP Integration (Beta)

TunaCode includes experimental Language Server Protocol support for real-time diagnostics. When an LSP server is detected in your PATH, it activates automatically.

**Supported languages:**
| Language   | LSP Server                    |
| ---------- | ----------------------------- |
| Python     | `ruff server`                 |
| TypeScript | `typescript-language-server`  |
| JavaScript | `typescript-language-server`  |
| Go         | `gopls`                       |
| Rust       | `rust-analyzer`               |

Diagnostics appear in the UI when editing files. This feature is beta - expect rough edges.

## Discord Server

Join our official discord server to receive help, show us how you're using tunacode, and chat about anything LLM.

[<img src="https://discord.com/api/guilds/1447688577126367346/widget.png?style=banner3" alt="Discord Banner 3"/>](https://discord.gg/TN7Fpynv6H)

## License

MIT
