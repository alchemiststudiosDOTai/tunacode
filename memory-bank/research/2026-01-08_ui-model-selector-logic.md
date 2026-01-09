# Research – UI Model Selector Logic
**Date:** 2026-01-08
**Owner:** Claude Agent
**Phase:** Research

## Goal
Map the complete UI model selector logic including data structures, screen flow, state management, and propagation to the agent core.

## Findings

### Architecture Overview

The model selector uses a **two-stage modal workflow**:
1. `ProviderPickerScreen` - Select provider (e.g., "anthropic", "openrouter")
2. `ModelPickerScreen` - Select specific model within that provider

Both screens use Textual's `Screen[str | None]` generic pattern, returning selected values via `dismiss()` callbacks.

### Key Files

| File | Purpose |
|------|---------|
| `src/tunacode/ui/screens/model_picker.py` | Two picker screen implementations (304 lines) |
| `src/tunacode/ui/commands/__init__.py` | `/model` command and callback chain (lines 92-138) |
| `src/tunacode/configuration/models.py` | Registry loading and query functions |
| `src/tunacode/configuration/models_registry.json` | Provider/model metadata (841KB JSON) |
| `src/tunacode/configuration/pricing.py` | Pricing lookup and formatting |
| `src/tunacode/core/state.py` | Session state with `current_model` field |
| `src/tunacode/ui/widgets/resource_bar.py` | Model display in status bar |

### Model String Format

Models use composite key format: `"provider:model_id"`

Examples:
- `"anthropic:claude-3-5-sonnet-20241022"`
- `"openrouter:openai/gpt-4.1"`
- `"openai:gpt-4o"`

Parsed by `parse_model_string()` at `models.py:16-31`.

---

## Data Flow

### 1. Command Trigger

**Entry Point:** `/model` command

```
User types "/model"
    ↓
handle_command() at app.py:322
    ↓
ModelCommand.execute() at commands/__init__.py:97
    ↓
Two paths:
  A) With args: Direct model set (lines 101-109)
  B) No args: Push ProviderPickerScreen (lines 134-137)
```

### 2. Screen Navigation Flow

```
ProviderPickerScreen.__init__(current_model)
    ├── Extracts current_provider from model string (line 100)
    ├── compose() loads providers via get_providers() (line 105)
    └── _rebuild_options() populates OptionList (line 114-139)

User selects provider → dismiss(provider_id)
    ↓
on_provider_selected() callback (commands/__init__.py:127-132)
    ↓
ModelPickerScreen.__init__(provider_id, current_model)
    ├── Loads models via get_models_for_provider() (line 225)
    ├── Adds pricing display via get_model_pricing() (line 252)
    └── _rebuild_options() populates OptionList (line 234-268)

User selects model → dismiss(f"{provider_id}:{model_id}")
    ↓
on_model_selected() callback (commands/__init__.py:118-125)
```

### 3. State Updates (on model selection)

```python
# commands/__init__.py:118-125
session.current_model = full_model              # Line 120
user_config["default_model"] = full_model       # Line 121
session.max_tokens = get_model_context_window() # Line 122
save_config(state_manager)                      # Line 123
app._update_resource_bar()                      # Line 124
app.notify(f"Model: {full_model}")              # Line 125
```

### 4. Agent Propagation

```
Next user request
    ↓
_process_request() at app.py:254
    ├── Reads: model_name = session.current_model (line 264)
    └── Passes to process_request(model=ModelName(model_name)) (line 272)
          ↓
get_or_create_agent() at agent_config.py:360
    ├── Checks session cache: session.agents[model] (line 367)
    ├── Checks module cache: _AGENT_CACHE[model] (line 376)
    └── Creates new agent via _create_model_with_retry() (line 306)
          ├── Parses provider:model string
          ├── Anthropic → AnthropicModel + AnthropicProvider
          └── Others → OpenAIChatModel + OpenAIProvider
```

---

## Key Patterns / Solutions Found

### 1. Two-Stage Modal Pattern
- **Location:** `model_picker.py:58-304`
- Reduces cognitive load via hierarchical navigation
- Clear separation: provider screen knows nothing about models

### 2. Callback Chain Pattern
- **Location:** `commands/__init__.py:118-137`
- Screens don't mutate state directly
- Return values via `dismiss()` → caller handles state updates
- Enables clean cancellation handling (None return)

### 3. Shared Filter Logic
- **Function:** `_filter_visible_items()` at `model_picker.py:16-36`
- Case-insensitive substring matching
- Limit applied only when unfiltered (50 items max)
- Truncation notice for user feedback

### 4. Deferred Initialization
- **Pattern:** `call_after_refresh(self._rebuild_options)` (lines 112, 232)
- Ensures OptionList is mounted before population
- Avoids Textual async rendering race conditions

### 5. Composite Key Registry
- **Format:** `registry[provider_id]["models"][model_id]`
- Enables namespacing across providers
- Single JSON file source of truth (841KB)

### 6. Two-Level Agent Caching
- **Module cache:** `_AGENT_CACHE` - survives across requests
- **Session cache:** `session.agents` - backward compatibility
- Version hash invalidates on config change

---

## Component Details

### ProviderPickerScreen (lines 58-174)

| Component | Location | Purpose |
|-----------|----------|---------|
| `_current_model` | Line 99 | Full model string for context |
| `_current_provider` | Line 100 | Provider ID for highlighting |
| `_all_providers` | Line 101 | Cached `[(name, id), ...]` |
| `_filter_query` | Line 102 | Current search text |
| `compose()` | Lines 104-112 | Creates filter input + option list |
| `_rebuild_options()` | Lines 114-139 | Filter + populate options |
| `on_input_changed()` | Lines 141-146 | Live filter on keystroke |
| `on_key()` | Lines 148-164 | Focus management (up/down/esc) |
| `on_option_list_option_selected()` | Lines 166-169 | Selection → dismiss |

### ModelPickerScreen (lines 176-304)

| Component | Location | Purpose |
|-----------|----------|---------|
| `_provider_id` | Line 217 | Provider from step 1 |
| `_current_model_id` | Line 220 | Model ID for highlighting |
| `_all_models` | Line 221 | Cached `[(name, id), ...]` |
| `_rebuild_options()` | Lines 234-268 | Filter + populate + **pricing** |
| Pricing lookup | Line 252 | `get_model_pricing(full_model)` |
| Pricing format | Line 254 | `"Model Name  $3.00/$15.00"` |
| Selection | Lines 295-299 | Reconstructs `f"{provider}:{model}"` |

### Resource Bar Display (lines 56-183)

| Field | Source | Format |
|-------|--------|--------|
| Model name | `session.current_model` | Raw string |
| Token usage | `session.total_tokens` | Circle + percentage |
| Session cost | `session.session_total_usage["cost"]` | `"$X.XX"` |

Token usage circles change based on remaining context:
- `> 87.5%` → `●` (full, green)
- `> 62.5%` → `◕` (yellow if < 60%)
- `> 37.5%` → `◑`
- `> 12.5%` → `◔` (red if < 30%)
- `≤ 12.5%` → `○` (empty)

---

## State Storage

### Runtime State
```python
# state.py:47
SessionState.current_model: ModelName  # Active model

# state.py:87
SessionState.max_tokens: int  # Context window size
```

### Persistent State
```python
# User config at ~/.config/tunacode.json
{
    "default_model": "openrouter:openai/gpt-4.1",
    "settings": {
        "context_window_size": 200000,
        ...
    }
}
```

### Session Persistence
```python
# Session file at ~/.tunacode/sessions/{project}_{session}.json
{
    "current_model": "anthropic:claude-3-5-sonnet-20241022",
    ...
}
```

---

## Knowledge Gaps

1. **No model validation:** Model names are not validated against registry before use
2. **No error handling in picker:** Invalid registry data could cause crash
3. **Hardcoded fallback:** `app.py:264` falls back to `"openai/gpt-4o"` (note: different format than registry)
4. **Provider inference:** `agent_config.py:333-334` infers provider from model name prefix (fragile)

---

## References

### Primary Files
- `src/tunacode/ui/screens/model_picker.py` - Main picker implementation
- `src/tunacode/ui/commands/__init__.py` - Command and callback handling
- `src/tunacode/configuration/models.py` - Registry functions
- `src/tunacode/configuration/pricing.py` - Cost calculations

### Supporting Files
- `src/tunacode/core/state.py` - Session state management
- `src/tunacode/ui/widgets/resource_bar.py` - Status display
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent creation
- `src/tunacode/configuration/defaults.py` - Default configuration

### Constants
- `MODEL_PICKER_UNFILTERED_LIMIT = 50` at `constants.py:41`
- `DEFAULT_CONTEXT_WINDOW = 200000` at `constants.py:35`
- Default model: `"openrouter:openai/gpt-4.1"` at `defaults.py:12`
