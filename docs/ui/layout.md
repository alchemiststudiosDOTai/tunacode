# Application Layout

**Date:** 2026-01-14
**Scope:** UI / Layout
**Status:** Canonical

## Overview

The Tunacode TUI uses a vertical stack layout to maximize the reading area while keeping the input context stable. The main application screen is divided into distinct functional zones.

## Main Screen Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Resource Bar (Model, Context usage)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Viewport] (RichLog)                                       │
│  - Scrollable history of the session                        │
│  - Contains User messages, Agent responses, Tool outputs    │
│  - Takes up remaining available space                       │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [Streaming Output] (Static)                                │
│  - Fixed panel anchored to the bottom of the viewport       │
│  - Visible ONLY during active agent generation              │
│  - Auto-expands to max 50% height, then scrolls internal    │
│  - Displays the live token stream                           │
├─────────────────────────────────────────────────────────────┤
│  [Input Area] (TextArea)                                    │
│  - Multi-line editor for user input                         │
│  - Auto-complete popups appear here                         │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Viewport (`#viewport`)
The primary container for the session history. It uses a `RichLog` widget to render Markdown content, code blocks, and panels.
- **Behavior:** Scrolls independently.
- **Content:** Stores finalized interactions. Once an agent finishes generating, the content is moved here from the Streaming Output.

### 2. Streaming Output (`#streaming-output`)
A specialized dock that appears between the history and the editor.
- **Location:** Fixed above the editor.
- **Purpose:** Prevents the "jumpy" scrolling effect that occurs when streaming text directly into a long log. It keeps the active thought process static and focused.
- **Styling:** Has a bottom border to separate it from the editor.
- **Visibility:** Toggled via CSS `display: none` when inactive.

### 3. Input Area (`#editor`)
The user's command center.
- **Location:** Pinned to the bottom.
- **Features:** Syntax highlighting, multi-line support, and auto-completion overlay.

## Styling Philosophy

The layout adheres to the NeXTSTEP-inspired design system:
- **Borders:** clear separation between functional areas.
- **Padding:** Minimal padding to maximize information density in the terminal.
- **Hierarchy:** The flow is top-down (History -> Active -> Input).
