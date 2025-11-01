# tunacode

[![Fork](https://img.shields.io/badge/fork-MoonshotAI/kimi--cli-blue)](https://github.com/MoonshotAI/kimi-cli)
[![Commit Activity](https://img.shields.io/github/commit-activity/w/alchemiststudiosDOTai/tunacode)](https://github.com/alchemiststudiosDOTai/tunacode/graphs/commit-activity)

**This is a fork of [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli)** with persistent shell session support and other design/personal flavors choices.

Kimi CLI is a powerful CLI agent that helps you with software development tasks and terminal operations. This fork extends the original with stateful shell execution and other design/personal flavors choices.

> [!NOTE]
> **Fork Base:** Upstream v0.45 (2025-10-31)
>
> This fork includes ALL upstream features through v0.45, including:
> - OpenAI responses chat provider with think part UI
> - Image pasting support
> - Markdown rendering (`--no-markdown` option)
> - Model capabilities environment variable override (`KIMI_MODEL_CAPABILITIES`)
> - Session history replay when continuing
> - Basic Windows support (experimental)
> - Improved startup performance
>
> This fork is maintained independently. We gratefully acknowledge the original Kimi CLI team at MoonshotAI for creating the foundation of this project.

> [!IMPORTANT]
> This fork is currently in active development. 

## Key Differences from Upstream

This fork adds personal enhancements beyond the original Kimi CLI:

### Persistent Shell Sessions (Primary Feature)

### .claude commands/subagents/skills port over (in dev)

### pass your own prompts (in dev)

### extend custom tools (in dev)



This fork is published as a Python package. We recommend installing it with [uv](https://docs.astral.sh/uv/).

### Install uv (if not already installed)
Follow instructions at: https://docs.astral.sh/uv/getting-started/installation/

### Install This Fork

```sh
# From source (recommended for this fork)
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode
uv sync
uv run kimi
```

Alternatively, if published to PyPI under a different name:
```sh
uv tool install --python 3.13 tunacode-kimi-cli
```

Run `kimi --help` to check if installation was successful.

> [!IMPORTANT]
> Due to security checks on macOS, the first run may take 10+ seconds depending on your system.

## Upgrading

## Features

### Persistent Shell Sessions

**Enabled by default.** All bash commands execute in a long-running shell process that maintains state.

#### Configuration

In `~/.kimi/config.json`, persistent shell is enabled by default:

```json
{
  "persistent_shell": {
    "enabled": true,
    "timeout": 30,
    "working_directory": null
  }
}
```

#### CLI Options

```sh
# Use persistent shell (default)
kimi

# Disable persistent shell for this session
kimi --no-persistent-shell
```



### Shell Mode

Kimi CLI functions as both a coding agent and a shell. Press `Ctrl-X` to switch modes and run shell commands directly.

> [!NOTE]
> With persistent shell enabled in this fork, `cd` commands now work correctly and persist between commands!

### Zsh Integration

Use Kimi CLI with Zsh to enhance your shell with AI agent capabilities.

Install [zsh-kimi-cli](https://github.com/MoonshotAI/zsh-kimi-cli):

```sh
git clone https://github.com/MoonshotAI/zsh-kimi-cli.git \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli
```

Add to `~/.zshrc`:
```sh
plugins=(... kimi-cli)
```

Restart Zsh and press `Ctrl-X` to switch to agent mode.

### ACP Support

Kimi CLI supports [Agent Client Protocol](https://github.com/agentclientprotocol/agent-client-protocol) out of the box.

Example configuration for [Zed](https://zed.dev/) in `~/.config/zed/settings.json`:

```json
{
  "agent_servers": {
    "Kimi CLI": {
      "command": "kimi",
      "args": ["--acp"],
      "env": {}
    }
  }
}
```

### Using MCP Tools

Kimi CLI supports MCP config convention:

```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

Run with:
```sh
kimi --mcp-config-file /path/to/mcp.json
```

## Architecture & Documentation

This fork includes extensive architectural documentation:

- **[CLAUDE.md](./CLAUDE.md)**: Comprehensive project overview and development guidelines
- **[.claude/](./.claude/)**: Knowledge base with patterns, architecture decisions, and development history
- **Memory Bank**: Research and execution logs in `memory-bank/` directory

Key architectural highlights:
- Separation of concerns with modular tool system
- Type-first design with full type safety
- Constructor-based dependency injection
- Async-by-default I/O
- Production-grade error handling
- Comprehensive test coverage

## Development

Clone and prepare the development environment:

```sh
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode

make prepare  # prepare development environment
```

Common development commands:

```sh
uv run kimi           # run Kimi CLI
make format           # format code
make check            # run linting and type checking
make test             # run tests
make help             # show all make targets
```

### Running Tests

```sh
# All tests
uv run pytest tests -vv

# Persistent shell tests specifically
uv run pytest tests/test_shell_manager.py -vv
uv run pytest tests/test_bash.py -vv
```

## Contributing

We welcome contributions to this fork! Areas where contributions are especially valuable:

- Testing and bug reports for the persistent shell feature
- Documentation improvements
- Additional shell state management features
- Performance optimizations

For contribution guidelines, see [CONTRIBUTING.md](./CONTRIBUTING.md).

### Upstream Sync

This fork tracks upstream changes from [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli). We periodically sync with upstream to incorporate improvements and bug fixes.

## License

Same license as upstream Kimi CLI (see [LICENSE](./LICENSE)).

## Acknowledgments

This project builds on the excellent work of the Kimi CLI team at MoonshotAI. We're grateful for their creation of the original foundation that made this fork possible.

Upstream repository: https://github.com/MoonshotAI/kimi-cli
