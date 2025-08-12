# Getting Started with TunaCode

## 1. Installation

You can install TunaCode using one of the following methods.

### Prerequisites

- Python 3.10 or higher
- Git

### Option 1: One-line Install (Linux/macOS)

```bash
wget -qO- https://raw.githubusercontent.com/alchemiststudiosDOTai/tunacode/master/scripts/install_linux.sh | bash
```

### Option 2: pip install

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
