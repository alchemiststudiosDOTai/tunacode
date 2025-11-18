# Research – Input Display Truncation for Long User Prompts

**Date:** 2025-11-17 18:24:31
**Owner:** claude-agent
**Phase:** Research
**Git Commit:** 61527f476407fefb8680e00cc309fe4ff4b0c64a

## Goal

Research how user input is currently displayed in the CLI REPL to identify the minimal code change needed to truncate or indicate long input (e.g., show `[4000 chars]` instead of full text) while the user is typing.

## Problem Statement

When a user enters a long prompt in the REPL, they currently see the **entire text** displayed in the prompt_toolkit input buffer as they type. For very long inputs (thousands of characters), this creates visual clutter. The user wants to see a truncated indicator like `[4000 chars]` instead of the full text.

## Additional Search

Relevant search patterns for future investigation:
- `grep -ri "bottom_toolbar" .claude/`
- `grep -ri "rprompt" .claude/`
- `grep -ri "buffer.text" src/tunacode/ui/`

## Findings

### 1. Input Display Architecture

The user input display is handled through **prompt_toolkit**, NOT through post-submission echo:

- [prompt_manager.py:87-136](src/tunacode/ui/prompt_manager.py#L87-L136) → `PromptManager.get_input()` manages the interactive session
- [prompt_manager.py:122-127](src/tunacode/ui/prompt_manager.py#L122-L127) → `session.prompt_async()` renders the input buffer
- [input.py:74-115](src/tunacode/ui/input.py#L74-L115) → `multiline_input()` configures the session
- [repl.py:318](src/tunacode/cli/repl.py#L318) → Input is captured but **NOT echoed back** to console after submission

**Key insight:** The user sees their full text **only while typing** in the prompt_toolkit buffer. After submission, the text goes directly to the agent without being displayed.

### 2. Current Display Flow

```
User types → prompt_toolkit buffer → session.prompt_async() → renders in terminal
                                                                 ↓
                                                    Full text displayed in input area
```

After submission:
```
line = await ui.multiline_input() → execute_repl_request(line) → agent processes
                                                                  ↓
                                                         NO echo to console
```

### 3. Relevant Files and Why They Matter

| File | Lines | Why It Matters |
|------|-------|----------------|
| [src/tunacode/ui/prompt_manager.py](src/tunacode/ui/prompt_manager.py) | 87-136 | Core input session management - `session.prompt_async()` call at line 122 controls display |
| [src/tunacode/ui/prompt_manager.py](src/tunacode/ui/prompt_manager.py) | 104-118 | `get_prompt()` function - dynamically generates the prompt prefix, could add right prompt or bottom toolbar here |
| [src/tunacode/ui/input.py](src/tunacode/ui/input.py) | 74-115 | Configures multiline input session - where we'd add rprompt/bottom_toolbar parameters |
| [src/tunacode/cli/repl.py](src/tunacode/cli/repl.py) | 318-380 | REPL loop - confirms no post-submission echo |

### 4. Where Input Text is Displayed

**During typing:**
- prompt_toolkit's internal buffer rendering shows the full text
- The buffer content is at `session.app.current_buffer.text` (seen at [prompt_manager.py:110](src/tunacode/ui/prompt_manager.py#L110))

**After submission:**
- The text is NOT displayed back to the user
- It goes to [repl.py:380](src/tunacode/cli/repl.py#L380) → `execute_repl_request(line, state_manager)`

### 5. Prompt Toolkit Session Configuration

Current `session.prompt_async()` call at [prompt_manager.py:122-127](src/tunacode/ui/prompt_manager.py#L122-L127):

```python
response = await session.prompt_async(
    get_prompt,                    # Dynamic prompt function
    is_password=config.is_password,
    validator=config.validator,
    multiline=config.multiline,
)
```

**Missing parameters** that could help:
- `rprompt=` - Shows text on the right side of the prompt (could show char count)
- `bottom_toolbar=` - Shows a toolbar at the bottom (could show truncation indicator)

## Key Patterns / Solutions Found

### Option 1: Add Right Prompt (rprompt) - MINIMAL CHANGE

Add a right prompt that shows character count when input exceeds threshold:

**Location:** [src/tunacode/ui/prompt_manager.py:122-127](src/tunacode/ui/prompt_manager.py#L122-L127)

```python
def get_rprompt():
    if hasattr(session.app, "current_buffer"):
        text = session.app.current_buffer.text
        if len(text) > 500:  # threshold
            return HTML(f'<style fg="#808080">[{len(text)} chars]</style>')
    return ""

response = await session.prompt_async(
    get_prompt,
    rprompt=get_rprompt,  # ADD THIS
    is_password=config.is_password,
    validator=config.validator,
    multiline=config.multiline,
)
```

**Pros:** Minimal code change, shows char count on right side
**Cons:** Doesn't actually truncate the displayed text, just indicates length

### Option 2: Add Bottom Toolbar - MODERATE CHANGE

Add a bottom toolbar that shows `[Long input: 4000 chars - use Ctrl+K to view]`:

**Location:** [src/tunacode/ui/prompt_manager.py:87-136](src/tunacode/ui/prompt_manager.py#L87-L136)

```python
def get_bottom_toolbar():
    if hasattr(session.app, "current_buffer"):
        text = session.app.current_buffer.text
        if len(text) > 500:
            return HTML(f'<style bg="#333333" fg="#ffcc00">⚠ Long input: {len(text)} chars</style>')
    return ""

response = await session.prompt_async(
    get_prompt,
    bottom_toolbar=get_bottom_toolbar,  # ADD THIS
    is_password=config.is_password,
    validator=config.validator,
    multiline=config.multiline,
)
```

**Pros:** More visible indicator, doesn't interfere with prompt
**Cons:** Takes up terminal space, slightly more code

### Option 3: Input Processor with Smart Truncation - MODERATE COMPLEXITY

Use a prompt_toolkit **input processor** to transform the display of long text while keeping the full buffer intact.

**Location:** [src/tunacode/ui/prompt_manager.py](src/tunacode/ui/prompt_manager.py)

#### How It Works:

1. **You paste 10,000 characters** → The buffer stores all 10,000 chars (you can edit the full text)
2. **Display shows:** `Here is the start of your... [9700 chars] ...and the end of text`
3. **When you type/edit:** Display updates in real-time showing truncated version
4. **Cursor position:** Works normally - you can cursor through the full text, display adjusts

#### What You See:

**Normal input (< 500 chars):**
```
tunacode> Write me a function that does X
```

**Long input (10,000 chars pasted):**
```
tunacode> Here is a very long prompt that talks about this and that... [9700 chars] ...please help
```

**While editing in the middle:**
- Cursor moves through full text
- Display shows: first 200 chars + `[hidden count]` + last 100 chars
- You can still use arrow keys, backspace, etc. to edit anywhere

#### Implementation Details:

Add a **Processor** class that:
1. Checks if `buffer.text` length > 500 chars
2. If yes: slice text to `text[:200] + f" [...{len(text)-300} chars...] " + text[-100:]`
3. If no: show full text
4. Processor runs on every buffer update (as you type)

**Code location:** [src/tunacode/ui/prompt_manager.py:67-73](src/tunacode/ui/prompt_manager.py#L67-L73)

Add processor when creating PromptSession:
```python
from prompt_toolkit.layout.processors import Processor, Transformation

class TruncateProcessor(Processor):
    def apply_transformation(self, transformation_input):
        # Get the full buffer text
        text = transformation_input.buffer_control.buffer.text

        # If text is long, truncate display
        if len(text) > 500:
            truncated = (
                text[:200]
                + f" [...{len(text)-300} chars...] "
                + text[-100:]
            )
            # Return transformation with truncated display
            # But buffer still has full text for editing
            ...
```

**Pros:**
- Actually truncates the visual display
- Full text remains in buffer for editing
- Cursor navigation works normally
- Clean visual for long pastes

**Cons:**
- ~40-60 lines of code
- Need to handle cursor position mapping
- Slightly more complex than rprompt

## Recommended Solution: Option 1 (Right Prompt)

**Minimal change location:** [src/tunacode/ui/prompt_manager.py:122-127](src/tunacode/ui/prompt_manager.py#L122-L127)

Add 5 lines:
1. Define `get_rprompt()` function before the `session.prompt_async()` call
2. Add `rprompt=get_rprompt` parameter to `session.prompt_async()`

This provides immediate feedback about input length without altering the core display behavior or adding complex truncation logic.

## Knowledge Gaps

1. **User preference:** Should the indicator be:
   - Character count? `[4000 chars]`
   - Truncation warning? `[Long input]`
   - Both? `[Long input: 4000 chars]`

2. **Threshold:** What character count should trigger the display?
   - 500 chars?
   - 1000 chars?
   - Configurable?

3. **Alternative display:** Should we actually truncate the visible text, or just indicate length?

## References

- [prompt_toolkit Documentation - Right Prompt](https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#adding-a-right-prompt)
- [prompt_toolkit Documentation - Bottom Toolbar](https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#adding-a-bottom-toolbar)
- [src/tunacode/ui/prompt_manager.py](src/tunacode/ui/prompt_manager.py) - Current implementation
- [src/tunacode/ui/input.py](src/tunacode/ui/input.py) - Multiline input configuration
- [src/tunacode/ui/lexers.py](src/tunacode/ui/lexers.py) - Current FileReferenceLexer implementation
