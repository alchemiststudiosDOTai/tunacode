# Getting Started with TunaCode

## 1. Installation

You can install TunaCode using one of the following methods.

### Prerequisites

- Python 3.10 or higher
- Git
- UV (recommended) - Install from [astral.sh/uv](https://astral.sh/uv) or `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Option 1: One-line Install (Linux/macOS)

```bash
wget -qO- https://raw.githubusercontent.com/alchemiststudiosDOTai/tunacode/master/scripts/install_linux.sh | bash
```

### Option 2: UV install (recommended)

```bash
uv tool install tunacode-cli
```

### Option 3: pip install

```bash
pip install tunacode-cli
```

## 2. Configuration

After installation, you need to configure TunaCode with your preferred AI provider and API key.

### Supported Providers

TunaCode supports a variety of providers, including:

*   OpenAI
*   Anthropic
*   Google
*   OpenRouter (which gives you access to over 100 models)

### Setting Your API Key

You can set your API key and model upon first run. Here are some examples for different providers:

### OpenAI

```bash
tunacode --model "openai:gpt-4o" --key "sk-your-openai-key"
```

### Anthropic

```bash
tunacode --model "anthropic:claude-3.5-sonnet" --key "sk-ant-your-anthropic-key"
```

### Google

```bash
tunacode --model "google:gemini-1.5-pro-latest" --key "your-google-api-key"
```

### OpenRouter

```bash
tunacode --model "openrouter:google/gemini-flash-1.5" --key "sk-or-your-openrouter-key"
```

Your configuration will be saved in `~/.config/tunacode.json`. You can modify this file directly for more [advanced settings](../configuration/config-file-example.md).

## 3. Basic Usage

Once configured, you can start the TunaCode CLI with a simple command:

```bash
tunacode
```

This will launch the interactive REPL, where you can start interacting with the AI.

### Basic Commands

Here are a few essential commands to get you started:

| Command                  | Description                               |
| ------------------------ | ----------------------------------------- |
| `/help`                  | Show all available commands.              |
| `/model <provider:name>` | Switch to a different AI model.           |
| `/clear`                 | Clear the current conversation history.   |
| `!<command>`             | Execute a shell command directly.         |
| `exit`                   | Exit the TunaCode CLI.                    |

For more details, read [commands.md](commands.md)

## 4. How TunaCode Works

TunaCode is an AI assistant that helps you with your coding tasks. It's designed to be interactive and to give you fine-grained control over its actions.

To learn more about the tools available to the agent, see the [**Tools Guide**](tools.md).

## 5. Safety First

**Important:** TunaCode is a powerful tool that can modify your files. Always follow these best practices:

-   **Use Version Control:** Always work on a Git branch and commit your changes frequently.
-   **Review Changes:** Carefully review any changes the agent proposes before confirming them.
-   **Keep Backups:** Ensure you have backups of your important work.
TunaCode Getting Started

This guide reflects the current CLI and agent behavior as implemented in the codebase. It covers installation, first‑time setup, core usage, configuration, and common workflows.

What you’ll use
- Command: `tunacode`
- Python: 3.10 – 3.13
- Config file: `~/.config/tunacode.json`
- Templates dir: `~/.config/tunacode/templates/`

Requirements
- Python 3.10–3.13 available on your PATH
- A terminal on macOS, Linux, or WSL2 (Windows)
- At least one provider API key (OpenAI, Anthropic, Google Gemini, or OpenRouter)

Install
- uv tool (recommended): `uv tool install tunacode-cli`
- pip: `pip install tunacode-cli`
- pipx: `pipx install tunacode-cli`

Launch
- From any project directory, run: `tunacode`
- To show version: `tunacode --version`
- To force fresh setup: `tunacode --setup`
- Guided setup wizard: `tunacode --wizard`

First‑time setup
On first launch, TunaCode initializes your environment through several coordinated steps:
- Configuration: Loads or creates `~/.config/tunacode.json`, merges defaults, and validates settings
- Environment: Exports API keys from your config to the process environment
- Templates: Creates `~/.config/tunacode/templates/` for future customization

Setup wizard (recommended)
- Run `tunacode --wizard` to enter guided setup
- Step 1: Enter any keys you use (you can skip what you don’t need)
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY`
  - `OPENROUTER_API_KEY`
- Step 2: Choose a default model from a presented list (format: `provider:model-id`, e.g. `openai:gpt-4.1`)
- Your choices are saved to `~/.config/tunacode.json`

CLI overrides (quick start without editing files)
- You can set a key, model, base URL, and context window directly:
  - `tunacode --model openai:gpt-4.1 --key sk-...`
  - `tunacode --baseurl https://openrouter.ai/api/v1 --model openrouter:openai/gpt-4.1 --key sk-...`
  - `tunacode --context 200000`
- These values are merged into `~/.config/tunacode.json` and used immediately.

Configuration file
- Location: `~/.config/tunacode.json`
- Example structure:
  {
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
      "OPENAI_API_KEY": "",
      "ANTHROPIC_API_KEY": "",
      "GEMINI_API_KEY": "",
      "OPENROUTER_API_KEY": ""
    },
    "settings": {
      "enable_streaming": true,
      "max_iterations": 40,
      "context_window_size": 200000
    },
    "mcpServers": {}
  }
- Notes
  - If a selected model is missing a required key, TunaCode tries to pick a fallback based on any configured key.
  - Environment variables defined under `env` are exported when the app starts.

Updating
- In-app: `/update` attempts to detect your install method (uv tool, pipx, venv, pip) and upgrade in place
- Manual:
  - uv tool: `uv tool upgrade tunacode-cli`
  - pip: `pip install --upgrade tunacode-cli`
  - pipx: `pipx upgrade tunacode-cli`

Using the REPL
When TunaCode starts, it opens an interactive prompt.

Basics
- Type a request and press Enter to run the agent.
- Multi‑line input is supported; `Esc+Enter` often submits depending on your terminal.
- Shell escape: prefix a line with `!` to run a shell command (`!` alone opens an interactive shell).
- View help: `/help`

File references in prompts
- Use `@` references to inline files/dirs into your prompt:
  - `@path/to/file.py` → inserts the file wrapped in code fences
  - `@src/` → inserts immediate files in that directory
  - `@src/**` → inserts files recursively (with size and count safeguards)
- TunaCode tracks which files are referenced and uses them for context.

Models
- Show model options and search interactively: `/model` (with prompts)
- List all: `/model --list`
- Show details and routing options: `/model --info <model-id>`
- Set directly and persist: `/model <provider:model-id>` (auto‑saves as default)

Plan Mode
- Enter read‑only research mode: `/plan`
- In Plan Mode, only read‑only tools execute (e.g., `read_file`, `grep`, `glob`, `list_dir`).
- The agent can present a plan for approval, after which implementation proceeds.
- Exit manually: `/exit-plan`

Common commands
- `/help` — show commands by category
- `/clear` — clear history and file context
- `/refresh` — merge latest default config keys into your current config
- `/streaming on|off` — toggle streamed vs. full responses
- `/update` — update TunaCode
- `/model ...` — search, inspect, or set the model
- `/plan`, `/exit-plan` — manage plan mode
- `/quickstart` or `/qs` — run the interactive tutorial
- `/branch <name>` — create/switch to a new git branch
- `/init` — create or improve `AGENTS.md` with project guidance

Costs and streaming
- Streaming is enabled by default; disable via `/streaming off`.
- Session token usage and estimated cost are tracked and shown.

Troubleshooting
- “No configuration found”: Run `tunacode --wizard` to set up keys/models. TunaCode will still start with safe defaults.
- “Missing API key for model”: Provide the required key or pick a fallback model with `/model`.
- “Model not found”: Try `/model --info <model>` or search with `/model <query>`; then set `/model <provider:model>`.
- Reset setup at any time with `tunacode --setup`.
- If streaming output is jumpy in your terminal, toggle it off: `/streaming off`.

Advanced: Custom slash commands and templates
- Slash commands: Markdown files under one of these are auto‑discovered with precedence:
  - Project: `.tunacode/commands/` or `.claude/commands/`
  - User: `~/.tunacode/commands/` or `~/.claude/commands/`
- Templates: Place reusable scaffolds in `~/.config/tunacode/templates/`. Commands with shortcuts may appear directly in the REPL.

Uninstall
- uv tool: `uv tool uninstall tunacode-cli`
- pip: `pip uninstall tunacode-cli`
- pipx: `pipx uninstall tunacode`

That’s it — run `tunacode`, complete the wizard, and start coding with the agent.
