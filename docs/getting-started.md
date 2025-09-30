## Getting started

### CLI usage

| Command            | Purpose                            | Example                         |
| ------------------ | ---------------------------------- | ------------------------------- |
| `tunacode`            | Interactive TUI                    | `tunacode`                         |
| `tunacode "..."`      | Initial prompt for interactive TUI | `tunacode "fix lint errors"`       |
| `tunacode exec "..."` | Non-interactive "automation mode"  | `tunacode exec "explain utils.ts"` |

Key flags: `--model/-m`, `--ask-for-approval/-a`.

### Resuming interactive sessions

- Run `tunacode resume` to display the session picker UI
- Resume most recent: `tunacode resume --last`
- Resume by id: `tunacode resume <SESSION_ID>` (You can get session ids from /status or `~/.tunacode/sessions/`)

Examples:

```shell
# Open a picker of recent sessions
tunacode resume

# Resume the most recent session
tunacode resume --last

# Resume a specific session by id
tunacode resume 7f9f9a2e-1b3c-4c7a-9b0e-123456789abc
```

### Running with a prompt as input

You can also run tunacode CLI with a prompt as input:

```shell
tunacode "explain this codebase to me"
```

```shell
tunacode --full-auto "create the fanciest todo-list app"
```

That's it - tunacode will scaffold a file, run it inside a sandbox, install any
missing dependencies, and show you the live result. Approve the changes and
they'll be committed to your working directory.

### Example prompts

Below are a few bite-size examples you can copy-paste. Replace the text in quotes with your own task.

| ✨  | What you type                                                                   | What happens                                                               |
| --- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 1   | `tunacode "Refactor the Dashboard component to React Hooks"`                       | tunacode rewrites the class component, runs `npm test`, and shows the diff.   |
| 2   | `tunacode "Generate SQL migrations for adding a users table"`                      | Infers your ORM, creates migration files, and runs them in a sandboxed DB. |
| 3   | `tunacode "Write unit tests for utils/date.ts"`                                    | Generates tests, executes them, and iterates until they pass.              |
| 4   | `tunacode "Bulk-rename *.jpeg -> *.jpg with git mv"`                               | Safely renames files and updates imports/usages.                           |
| 5   | `tunacode "Explain what this regex does: ^(?=.*[A-Z]).{8,}$"`                      | Outputs a step-by-step human explanation.                                  |
| 6   | `tunacode "Carefully review this repo, and propose 3 high impact well-scoped PRs"` | Suggests impactful PRs in the current codebase.                            |
| 7   | `tunacode "Look for vulnerabilities and create a security review report"`          | Finds and explains security bugs.                                          |

### Memory with AGENTS.md

You can give tunacode extra instructions and guidance using `AGENTS.md` files. tunacode looks for `AGENTS.md` files in the following places, and merges them top-down:

1. `~/.tunacode/AGENTS.md` - personal global guidance
2. `AGENTS.md` at repo root - shared project notes
3. `AGENTS.md` in the current working directory - sub-folder/feature specifics

For more information on how to use AGENTS.md, see the [official AGENTS.md documentation](https://agents.md/).

### Tips & shortcuts

#### Use `@` for file search

Typing `@` triggers a fuzzy-filename search over the workspace root. Use up/down to select among the results and Tab or Enter to replace the `@` with the selected path. You can use Esc to cancel the search.

#### Image input

Paste images directly into the composer (Ctrl+V / Cmd+V) to attach them to your prompt. You can also attach files via the CLI using `-i/--image` (comma‑separated):

```bash
tunacode -i screenshot.png "Explain this error"
tunacode --image img1.png,img2.jpg "Summarize these diagrams"
```

#### Esc–Esc to edit a previous message

When the chat composer is empty, press Esc to prime “backtrack” mode. Press Esc again to open a transcript preview highlighting the last user message; press Esc repeatedly to step to older user messages. Press Enter to confirm and tunacode will fork the conversation from that point, trim the visible transcript accordingly, and pre‑fill the composer with the selected user message so you can edit and resubmit it.

In the transcript preview, the footer shows an `Esc edit prev` hint while editing is active.

#### Shell completions

Generate shell completion scripts via:

```shell
tunacode completion bash
tunacode completion zsh
tunacode completion fish
```

#### `--cd`/`-C` flag

Sometimes it is not convenient to `cd` to the directory you want tunacode to use as the "working root" before running tunacode. Fortunately, `tunacode` supports a `--cd` option so you can specify whatever folder you want. You can confirm that tunacode is honoring `--cd` by double-checking the **workdir** it reports in the TUI at the start of a new session.
