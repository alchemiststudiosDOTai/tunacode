# Keyboard Shortcuts

## Text Selection and Copy/Paste

Tunacode runs inside a Textual TUI, which captures mouse events. To use your terminal's native text selection:

| Terminal | Modifier Key | Action |
|----------|--------------|--------|
| Windows Terminal | **Shift** | Hold Shift + click and drag to select |
| Gnome Terminal | **Shift** | Hold Shift + click and drag to select |
| iTerm2 (macOS) | **Cmd** | Hold Cmd + click and drag to select |
| Other terminals | Varies | Check your terminal's documentation |

Once text is selected, use your terminal's copy shortcut:
- **Windows Terminal**: `Ctrl+Shift+C` to copy, `Ctrl+Shift+V` to paste
- **macOS**: `Cmd+C` to copy, `Cmd+V` to paste
- **Linux**: `Ctrl+Shift+C` to copy, `Ctrl+Shift+V` to paste (or middle-click to paste)

## Application Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Submit input |
| `Escape` | Cancel current stream |
| `Ctrl+P` | Pause/Resume streaming output |
| `1`, `2`, `3` | Quick response to tool confirmation (Yes/Yes+Skip/No) |
| `1`, `2` | Quick response to plan approval (Approve/Deny) |

## Bash Mode

Prefix your input with `!` to enter bash mode, which sends commands directly to the shell.
