# Research -- API Key UX Improvement

**Date:** 2026-02-19
**Owner:** agent
**Phase:** Research

## Goal

Map the current API key validation and error UX when a user selects a model without a configured key, and identify all touchpoints that need improvement to provide an empathetic, guided experience instead of a dead-end error.

## Problem Statement

When a user picks a model via the model picker and lacks the API key for that provider, the app:
1. Shows a transient toast notification ("Missing API key: OPENROUTER_API_KEY")
2. Writes a yellow hint to `rich_log` (with no config path on the picker flow)
3. Silently refuses to switch the model
4. Closes the picker screens, leaving the user stranded on the old model with no recovery path

No inline key entry is offered. No link to the provider's dashboard. No guidance on what to do next. The user has to know to either run `--setup` again or manually edit `~/.config/tunacode.json`.

## Findings

### Current Architecture

#### Config File Location
- **Path:** `~/.config/tunacode.json`
- **Defined in:** [`constants.py:26`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/constants.py#L26) (`CONFIG_FILE_NAME = "tunacode.json"`)
- **Assembled by:** [`configuration/settings.py:14-17`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/settings.py#L14) (`PathConfig`)

#### API Key Flow (Config -> Agent)

```
~/.config/tunacode.json
    |
    v
load_config() -> merge_user_config(defaults, user)   [user_config.py:30-70]
    |
    v
StateManager._session.user_config["env"]              [state.py:83]
    |
    v
_build_api_key_resolver(session)                       [agent_config.py:239-266]
    |  closure over env_config dict
    v
AgentOptions(get_api_key=resolver)                     [agent_config.py:381]
    |
    v
tinyagent calls resolver(provider_id) per request
```

**No `os.environ` fallback** -- API keys come exclusively from the JSON config file. The resolver has one fallback: `OPENAI_API_KEY` is tried as a universal fallback for non-OpenAI providers ([`agent_config.py:264`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/core/agents/agent_components/agent_config.py#L264)).

#### Relevant Files

| File | Role |
|------|------|
| [`ui/commands/model.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/commands/model.py) | `/model` command, validation gate, error messaging |
| [`ui/screens/model_picker.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/screens/model_picker.py) | Provider + model picker modals |
| [`ui/screens/setup.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/screens/setup.py) | First-run setup wizard with inline API key `Input` |
| [`configuration/models.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/models.py) | `validate_provider_api_key()`, `get_provider_env_var()` |
| [`configuration/defaults.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/defaults.py) | Default config shape with empty env vars |
| [`core/agents/agent_components/agent_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/core/agents/agent_components/agent_config.py) | `_build_api_key_resolver()`, agent creation |
| [`core/ui_api/configuration.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/core/ui_api/configuration.py) | Facade re-exporting config functions |
| [`ui/styles/modals.tcss`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/styles/modals.tcss) | CSS for `#api-key-input`, `#error-label` (from setup screen) |
| [`ui/renderers/errors.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/renderers/errors.py) | Error panel renderer (no API key-specific entry) |
| [`configuration/user_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/user_config.py) | `save_config()`, `load_config_with_defaults()` |

### Specific Issues Found

#### Issue 1: `validate_provider_api_key` ignores `os.environ`

[`configuration/models.py:112-125`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/models.py#L112) checks only `user_config["env"]`. A user with `ANTHROPIC_API_KEY` exported in their shell will see a false-positive validation failure, even though the key would work at runtime (since `_build_api_key_resolver` also only checks user_config, meaning it wouldn't work at runtime either -- both are consistent but both ignore the shell env).

#### Issue 2: Picker flow passes `show_config_path=False`

[`model.py:100-106`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/commands/model.py#L100) -- the picker callback (the more common, more interactive path) gives the user LESS information than the direct `/model provider:model` path which passes `show_config_path=True` at line 77. The user sees only a transient toast and no config file path.

#### Issue 3: No inline key entry after validation failure

After the picker is dismissed and validation fails, the user has NO way to enter the key without:
- Running `tunacode --setup` again (restarts everything)
- Manually editing `~/.config/tunacode.json` (requires knowing the path and format)

There is no "enter your key now" modal in the model selection flow.

#### Issue 4: No provider dashboard links

The registry at [`models_registry.json`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/models_registry.json) has provider data but no dashboard/signup URLs. A truly helpful UX would tell the user WHERE to get the key.

#### Issue 5: `AuthenticationError` has no specific recovery hints

[`ui/renderers/errors.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/renderers/errors.py) has `ERROR_SEVERITY_MAP` and `DEFAULT_RECOVERY_COMMANDS` but neither includes `AuthenticationError`. When the agent fails at runtime due to a missing key, the user gets a generic error panel with no API-key-specific guidance.

### Existing Reusable Patterns

The `SetupScreen` ([`setup.py:25-145`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/screens/setup.py#L25)) already has:
- `Input(password=True, id="api-key-input")` for secret key entry
- `Static("", id="error-label")` for inline validation feedback
- `get_provider_env_var(provider)` to resolve the correct env var
- `save_config()` to persist the key

CSS for these widgets exists in [`modals.tcss`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/styles/modals.tcss) (`#api-key-input`, `#error-label`).

## Key Patterns / Solutions Found

- **Inline key entry screen pattern**: `SetupScreen` provides a complete, tested blueprint for collecting API keys inline. A lightweight `ApiKeyScreen(Screen[str | None])` can be extracted from this pattern.

- **Screen chaining in Textual**: The model picker already chains `ProviderPickerScreen -> ModelPickerScreen` via `push_screen` callbacks. Adding a third screen (`ApiKeyScreen`) on validation failure follows the same pattern.

- **Config persistence**: `save_config(state_manager)` already handles writing `user_config["env"][env_var] = key` to disk. The new screen just needs to update `state_manager.session.user_config["env"]` and call save.

- **Fallback resolver**: `_build_api_key_resolver` captures `env_config` at agent creation time. After saving a new key, `invalidate_agent_cache()` forces re-creation, which re-captures the updated env dict.

## Knowledge Gaps

1. **Provider dashboard URLs**: The `models_registry.json` does not contain signup/dashboard URLs for providers. Adding these would require a schema extension and data collection effort. Out of scope for the initial fix but worth tracking.

2. **`os.environ` policy**: Is there an intentional design decision to NOT read API keys from `os.environ`? The current codebase is consistent (neither validation nor the resolver checks `os.environ`), but users coming from other tools may expect env vars to work. Need to decide if this should be supported.

3. **Compaction key error**: [`compaction/controller.py:439`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/core/compaction/controller.py#L439) raises `MissingCompactionApiKeyError` but it's caught and swallowed at line 243-248 (compaction skips silently). This is a separate UX concern but related.

## Proposed Solution Direction

**Create an `ApiKeyEntryScreen`** that:
1. Is pushed when `_validate_provider_api_key_with_notification` fails during model selection
2. Shows the provider name, the required env var name, and a password input
3. On submit: saves key to `user_config["env"]`, persists config, proceeds with model switch
4. On cancel: returns to the model picker (not the main chat)

**Flow change:**
```
Current:  Pick provider -> Pick model -> Validation fails -> Toast + dead end
Proposed: Pick provider -> Pick model -> Validation fails -> ApiKeyEntryScreen -> Save & switch
```

**Quick wins (no new screen):**
1. Always pass `show_config_path=True` from the picker callback
2. Add `AuthenticationError` to `ERROR_SEVERITY_MAP` with recovery hints
3. Make the `rich_log` message more actionable (include config path always)

## References

- [`ui/commands/model.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/commands/model.py) -- validation gate and error messaging
- [`ui/screens/setup.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/screens/setup.py) -- reusable API key input pattern
- [`ui/screens/model_picker.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/screens/model_picker.py) -- screen chaining pattern
- [`configuration/models.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/configuration/models.py) -- validation logic
- [`core/agents/agent_components/agent_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/core/agents/agent_components/agent_config.py) -- API key resolver
- [`ui/renderers/errors.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b8264e16/src/tunacode/ui/renderers/errors.py) -- error rendering (needs API key entry)
