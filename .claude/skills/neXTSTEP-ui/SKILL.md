---
name: neXTSTEP-ui
description: Design philosophy and UI guidelines based on NeXTSTEP User Interface Guidelines (1993). Use when designing interfaces (TUI, GUI, web apps, dashboards) that need clear information hierarchy, intuitive controls, and user-respecting interaction patterns. Especially relevant for developer tools, data-dense interfaces, and applications requiring high information density without cognitive overload.
---

# NeXTSTEP Design Philosophy

Principles from the NeXTSTEP User Interface Guidelines (Release 3, 1993)—the DNA of modern computing interfaces.

## Core Principles

### Consistency
Objects that look the same should act the same. Objects that act the same should look the same. Users build mental models; reward them.

### User Control
The user decides what happens next. The computer extends the user's will—it never obstructs it.

**On modes:** Avoid arbitrary modes (periods when only certain actions are permitted). Modes usurp the user's prerogative. When modes are necessary, they must be:
- Freely chosen by the user
- Visually apparent at all times
- Easy to exit
- Keep user in control

### Acting for the User
When in doubt, don't. Better to do too little than too much. If acting on user's behalf, the result must be identical to if the user had acted themselves.

### Naturalness
Graphical objects don't need to resemble physical objects superficially—but they must *behave* as real-world experience would predict. Objects stay where put. Controls feel like controls. This is what "intuitive" means.

## Action Paradigms

Every interaction falls into one of three paradigms:

### 1. Direct Manipulation
Objects respond directly to mouse/pointer actions. A window comes forward when clicked. A slider knob moves when dragged. Most intuitive paradigm—use for position, size, arrangement.

### 2. Targeted Action
Controls (buttons, commands) act on a target. User selects target first, then chooses action. Example: select text → click Bold. Powerful because one control can act on many target types.

### 3. Modal Tool
User selects tool from palette; subsequent actions interpreted through that tool. Acceptable when:
- Mode is visible (cursor changes, tool highlighted)
- Mode is user-chosen
- Exit is obvious and immediate
- Mimics real-world tool selection

**Use modal tools when:** An operation type will be repeated many times (drawing lines, placing objects).
**Don't use when:** User would constantly switch tools between actions.

## Information Hierarchy & Zoning

Divide interface into zones with distinct purposes. Users learn where to look.

```
┌─────────────────────────────────────────────────┐
│              PERSISTENT STATUS                  │  Glanceable, rarely changes
│         (resources, mode, identity)             │  Top or very top
├─────────────────────────────────────────────────┤
│                                                 │
│                 PRIMARY VIEWPORT                │  Maximum real estate
│              (content, workspace)               │  User focus lives here
│                                                 │
├───────────┬─────────────────────┬───────────────┤
│  SPATIAL  │     SELECTION       │   AVAILABLE   │  Context for next action
│  CONTEXT  │     CONTEXT         │   ACTIONS     │  What's loaded, what's possible
│  (where)  │     (what)          │   (can do)    │
├───────────┴─────────────────────┴───────────────┤
│                 INPUT / COMMAND                 │  Muscle memory location
│               (user action zone)                │  Bottom for CLI patterns
└─────────────────────────────────────────────────┘
```

**Key insight from StarCraft UI:** High information density works when zones are consistent and purpose is clear. Resources always top-right. Minimap always bottom-left. Selection always bottom-center. Actions always bottom-right. Users never hunt.

## Control Selection Guide

### Use Buttons When:
- Starting an action (one-state/action button)
- Toggling a binary state (two-state button)
- **Never** use buttons with more than two states—too hard to convey meaning

### Button Labels:
- One-state: verb or verb phrase ("Find", "Save", "Print")
- Label describes what *will happen*, not current state
- Dim (gray out) when action unavailable—disabled button must not respond at all
- Add "..." suffix if button opens a panel/dialog

### Use Pop-up Lists When:
- Setting state from multiple options (one-of-many)
- Space is constrained
- The current selection should be visible

### Use Radio Buttons When:
- One-of-many selection
- All options should be visible simultaneously
- Small number of options (2-5)

### Use Switches/Checkboxes When:
- Independent on/off options
- Multiple can be selected (unrestricted relationship)

### Use Text Fields When:
- Impossible to enumerate all valid values
- Free-form input needed
- Always pair with a button showing what Return does

### Use Sliders When:
- Setting a value in a bounded range
- Direct feedback on continuous scale
- Alternate-drag should enable fine-tuning mode

### Use Browsers/Lists When:
- Hierarchical data (browser)
- Selection from enumerable set (list)
- Double-click should equal Return key action

## Feedback Principles

### Visual Feedback
- Controls change appearance immediately on mouse-down
- Appearance during click reflects what's about to happen
- User must always see result of their action

### State Indication
- Current state shown through highlighting, position, or imagery
- Never rely solely on labels to show state
- Disabled controls are dimmed AND non-responsive

### Scrolling
- Knob size represents visible portion relative to whole
- Knob position represents current location
- Alternate-drag enables fine-tuning mode
- Scroll buttons: click = one line, press = continuous, Alternate = one page

## Text & Labels

- Capitalize like titles (first word, last word, and principal words)
- Be succinct—labels are shorthand
- Commands that open panels end with "..."
- Avoid jargon; prefer familiar terms

## Window Behavior

- Windows stay where user puts them
- Active window receives keyboard input
- Clicking a window brings it forward
- Close, minimize, resize controls in consistent locations
- Panels (secondary windows) support main window's task

## Anti-Patterns to Avoid

1. **Hidden modes** — User doesn't know different rules apply
2. **Inconsistent controls** — Same-looking things behave differently
3. **Surprising automation** — System acts without user initiation
4. **Disabled without indication** — Controls that silently fail
5. **Fighting muscle memory** — Putting input where users don't expect
6. **Information hunting** — Critical info in inconsistent locations
7. **Modal dialogs for non-critical info** — Interrupting user flow unnecessarily

## TUI-Specific Adaptations

For terminal user interfaces, adapt these principles:

```
┌─ Model: gpt-4 ─┬─ Tokens: 1.2k ─┬─ Status: ready ─┐  ← status bar
│                                                    │
│  Main content area                                 │  ← viewport
│  (conversation, output, editor)                    │
│                                                    │
├──────────┬─────────────────┬──────────────────────┤
│ ~/proj   │ files.py        │ ● search  ● bash     │  ← context zones
│          │ config.json     │ ● read    ● write    │
├──────────┴─────────────────┴──────────────────────┤
│ >                                                  │  ← input (CLI convention)
└────────────────────────────────────────────────────┘
```

- Respect CLI convention: input at bottom, output scrolls up
- Use box-drawing characters for clear zone separation
- Status bar: left=identity, center=metrics, right=state
- Color sparingly: highlight actionable items and state changes
- Keyboard shortcuts visible but not cluttering

## Testing Principle

> "The success of an application's interface depends on real users. There's no substitute for having users try out the interface—even before there's any functionality behind it—to see whether it makes sense to them."

Test early. Test with real users. Test before implementation.

You can also read the PDF version of the NeXTSTEP User Interface Guidelines (1993) for more detailed information. IN skills/neXTSTEP-ui/NeXTSTEP_User_Interface_Guidelines_Release_3_Nov93.pdf
