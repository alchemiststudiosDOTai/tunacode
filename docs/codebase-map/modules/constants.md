---
title: Constants Module
path: src/tunacode/constants.py
type: file
depth: 0
description: Global constants, UI text, and magic strings
exports: [UI_COLORS, TOOL_NAMES, ERROR_MESSAGES]
seams: [M]
---

# Constants Module

## Purpose
Centralizes global constants, magic strings, UI text, error messages, and application-wide fixed values.

## Constant Categories

### UI Colors and Styling

**UI_COLORS Dictionary:**
```python
{
  "primary": "#3B82F6",
  "success": "#10B981",
  "warning": "#F59E0B",
  "error": "#EF4444",
  "muted": "#6B7280",
  # ... more colors
}
```

**Theme Building Functions:**
- **build_tunacode_theme()** - Default theme
- **build_nextstep_theme()** - NeXTSTEP-inspired theme

### Tool Names

**TOOL_NAMES:**
- bash
- glob
- grep
- read_file
- write_file
- update_file
- list_dir
- web_fetch
- todowrite
- todoread
- todoclear
- react

### UI Constants

**Panel Dimensions:**
- **TOOL_PANEL_WIDTH** - Default width for tool panels
- **RICHLOG_MAX_LINES** - Maximum lines in log
- **TRUNCATION_THRESHOLD** - Content truncation point

**File Path Indicators:**
- **HOOK_ARROW** - Hook arrow used for file path params
- **HOOK_ARROW_PREFIX** - Arrow plus space prefix for Zone 2 file paths

**CSS Classes:**
- **RICHLOG_CLASS_PAUSED** - Styling for paused state
- **RICHLOG_CLASS_STREAMING** - Styling for streaming state

**Timeouts:**
- **STREAM_THROTTLE_MS** - Streaming update throttle
- **TOOL_TIMEOUT_DEFAULT** - Default tool timeout

### Error Messages

**Standardized Messages:**
- **ERROR_FILE_NOT_FOUND** - File missing template
- **ERROR_PERMISSION_DENIED** - Permission error template
- **ERROR_TIMEOUT** - Timeout message template
- **ERROR_INVALID_INPUT** - Invalid input message

### UI Text

**Status Messages:**
- Processing status text
- Completion messages
- Error prefixes
- Tool descriptions

**Labels:**
- Button labels
- Field labels
- Menu items
- Headers

### Application Constants

**Version Information:**
- **VERSION** - Application version
- **BUILD_DATE** - Build timestamp

**Configuration:**
- **CONFIG_DIR** - Default config directory
- **SESSIONS_DIR** - Sessions storage directory
- **TEMPLATES_DIR** - Templates directory

**Limits:**
- **MAX_ITERATIONS** - Default agent loop limit
- **MAX_TOKENS** - Default context limit
- **MAX_FILE_SIZE** - File size limit for tools

### Magic Strings

**Markers:**
- **ToolName.SUBMIT** - "submit" tool name used for completion signaling
- **CONFIRMATION_PROMPT** - Confirmation marker
- **STREAMING_START** - Stream start marker
- **STREAMING_END** - Stream end marker

**Patterns:**
- File extension patterns
- Ignore patterns
- Validation patterns

## Usage Examples

### UI Styling
```python
from tunacode.constants import UI_COLORS

color = UI_COLORS["primary"]
```

### Error Messages
```python
from tunacode.constants import ERROR_MESSAGES

msg = ERROR_MESSAGES["FILE_NOT_FOUND"].format(path="file.txt")
```

### Tool Names
```python
from tunacode.constants import TOOL_NAMES

if tool_name == TOOL_NAMES["bash"]:
    # Handle bash tool
    pass
```

## Integration Points

- **ui/** - UI styling and text
- **tools/** - Tool names and descriptions
- **ui/renderers/** - Panel dimensions and styling
- **All modules** - Error messages and constants

## Seams (M)

**Modification Points:**
- Add new color schemes
- Customize UI text
- Add new constants
- Modify error message templates

**Best Practices:**
- Use descriptive constant names
- Group related constants
- Document magic strings
- Avoid hardcoding values
- Use constants for all repeated values
