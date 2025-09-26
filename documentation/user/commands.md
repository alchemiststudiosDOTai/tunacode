# User Commands

This document provides a detailed overview of all the user-facing commands available in TunaCode. You can execute these commands directly in the interactive REPL by prefixing them with a forward slash (`/`).

## System Commands

These commands are for managing the TunaCode application itself.

- **`/help`**: Displays a list of all available commands, grouped by category.

- **`/refresh`**: Refreshes your local configuration with the latest defaults. This is useful after updating TunaCode to ensure you have the latest settings.

- **`/streaming`**: Toggles the streaming of AI responses on or off. When on, the response will be displayed as it's being generated. When off, the full response will be shown only after it's complete.

- **`/update`**: Updates TunaCode to the latest version available on PyPI.

- **`/template`**: Manages and uses templates for pre-approved sets of tools and prompts. You can list, load, create, and clear templates.

- **`/compact`**: Summarizes the current conversation history to reduce the number of tokens sent to the model. This is useful in long conversations to keep the context relevant and manage costs.

## Navigation Commands

These commands help you manage the conversation history.

- **`/clear`**: Clears the screen and the entire message history of the current session.

## Development Commands

These commands are designed to assist with your development workflow.

- **`/yolo`** (You Only Live Once): Toggles YOLO mode. When enabled, all tool confirmations are skipped, allowing the agent to execute file modifications and commands without asking for your approval. Use with caution.

- **`/branch <branch-name>`**: Creates a new Git branch and switches to it.

- **`/init`**: Analyzes the codebase and creates or updates a `AGENTS.md` file with project-specific context, such as build commands and coding standards.
- **`/todo`**: Manages a to-do list for the current task. You can add, list, update, and remove to-do items.

- **`/plan`**: Enters "Plan Mode," a read-only research phase where the agent can only use tools that don't modify your files (`read_file`, `grep`, `list_dir`, `glob`). This is useful for researching a task before making changes.

- **`/exit-plan`**: Exits "Plan Mode" and returns to the normal mode where all tools are available.

## Model Commands

These commands are for managing the AI model used by the agent.

- **`/model <provider:model-name> [default]`**: Switches the AI model for the current session. You can also set a model as the default for future sessions.

## Debug Commands

These commands are for debugging and troubleshooting the agent's behavior.

- **`/dump`**: Dumps the current message history to the console, including all system prompts and tool calls. This is useful for understanding the agent's reasoning process.

- **`/thoughts`**: Toggles the display of the agent's thought process. When enabled, you will see the agent's reasoning and plans before it executes a tool or responds.

- **`/iterations <number>`**: Sets the maximum number of iterations the agent can perform for a single task. This is useful for complex tasks that require multiple steps of reasoning and tool use.

- **`/fix`**: Attempts to fix orphaned tool calls that can cause API errors. This is useful when the agent gets stuck in a loop.

- **`/parsetools`**: Manually triggers the parsing of JSON tool calls from the last response. This is a fallback for when the structured tool calling fails.

## Utility Commands

- **`/command-reload`**: Reloads all slash commands from the command directories. This is useful when developing or modifying custom slash commands, as it allows you to test changes without restarting TunaCode.

## Built-in Commands

- **`exit`**: Exits the TunaCode application.

## Custom Slash Commands

TunaCode supports user-defined slash commands written in Markdown. These commands can be created without modifying the TunaCode codebase.

### How Slash Commands Work

Slash commands are discovered from these directories (in order of priority):
1. `.tunacode/commands/` in your project directory
2. `.claude/commands/` in your project directory
3. `~/.tunacode/commands/` in your home directory
4. `~/.claude/commands/` in your home directory

Commands are invoked using their namespace and path: `/namespace:path:to:command`

### Creating a Slash Command

To create a custom command:

1. Create a markdown file in one of the command directories
2. Optionally add YAML frontmatter for configuration
3. Write your command prompt/template

Example: `.tunacode/commands/review.md`
```markdown
---
description: "Review code for best practices"
allowed-tools: ["read_file", "grep"]
---

Please review the following files for code quality: $ARGUMENTS
```

Usage: `/project:review src/main.py`

### Template Features

Slash commands support:
- `$ARGUMENTS` - Command arguments
- `$ENV_VAR` - Environment variables
- `@file.py` - Include file contents
- `@@*.py` - Include files by pattern
- `!`command`` - Execute shell commands

For detailed information on creating custom commands, see the [development documentation](../development/creating-custom-commands.md).
