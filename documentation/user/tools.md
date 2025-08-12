# Tools

This document provides an overview of the tools available to the TunaCode agent.

## Tools at Your Disposal

The agent uses a set of tools to interact with your project. You can think of these as the agent's hands. You can find the source code for all tools in the `src/tunacode/tools/` directory.

Here are the main tools and what they do:

*   **`read_file`**: Reads the content of a specified file.
*   **`write_file`**: Creates a new file with the specified content.
*   **`update_file`**: Modifies an existing file by replacing a block of text.
*   **`list_dir`**: Lists the files and directories in a specified path.
*   **`glob`**: Finds files matching a specific pattern (e.g., `*.py`, `src/**/*.js`).
*   **`grep`**: Searches for a pattern within files (similar to the `grep` command-line utility).
*   **`bash` / `run_command`**: Executes shell commands.
*   **`run_command`**: Executes simple shell commands.
*   **`bash`**: Executes advanced shell commands with environment control.
*   **`todo`**: Manages a to-do list for the current task.

## Safe and Fast Operations

TunaCode categorizes tools into two types for your safety and for performance:

*   **Read-Only Tools** (`read_file`, `grep`, `list_dir`, `glob`): These tools don't change your code. Because they are safe, TunaCode can run many of them at the same time (in parallel). This means that when the agent needs to understand your project, it can read multiple files at once, which is much faster than doing it one by one. You'll notice this as a significant speed-up in tasks that require reading a lot of files.

*   **Write/Execute Tools** (`write_file`, `update_file`, `bash`): These tools can modify your files or run commands. For your safety, TunaCode will always ask for your confirmation before using these tools. You will be shown a diff of the proposed changes before they are applied.
