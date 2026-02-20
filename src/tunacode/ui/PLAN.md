# Plan: Refactor `lifecycle.py` to `AppLifecycle`

## Current State

The `src/tunacode/ui/lifecycle.py` module contains free functions:

| Function | Responsibility |
|----------|----------------|
| `on_mount(app)` | Entry point — theme, session metadata, setup-vs-repl branch |
| `_on_setup_complete(app, completed)` | Setup dismiss callback |
| `_start_repl(app)` | Logger wiring, request worker, timer, welcome |
| `on_unmount(app)` | Stop timer + save session |

### Problems

- Lifecycle state is implicit and spread across function scope + `app` fields.
- `app` is threaded through every call.
- Setup callback indirection (`_on_setup_callback`) adds noise.
- `_start_repl` can be reached from two paths with no explicit idempotency guard.
- Mount/unmount logic is not represented as one cohesive object.

## Proposed Design

Create an `AppLifecycle` class that owns lifecycle sequencing and mount/unmount flow.

```python
class AppLifecycle:
    """Manage TunaCode app lifecycle stages."""

    def __init__(self, app: TextualReplApp) -> None:
        self._app = app
        self._state_manager = app.state_manager
        self._repl_started = False

    def mount(self) -> None:
        self._init_theme()
        self._init_session_metadata()
        if self._app._show_setup:
            self._push_setup_screen()
            return
        self._start_repl()

    async def unmount(self) -> None:
        self._stop_slopgotchi_timer()
        await self._state_manager.save_session()

    def _push_setup_screen(self) -> None:
        self._app.push_screen(SetupScreen(self._state_manager), self._on_setup_complete)

    def _on_setup_complete(self, completed: bool | None) -> None:
        if completed:
            self._app._update_resource_bar()
        self._start_repl()

    def _start_repl(self) -> None:
        if self._repl_started:
            return
        self._repl_started = True
        ...
```

## App Integration (Critical)

`TextualReplApp` must persist one lifecycle instance:

```python
self._lifecycle = AppLifecycle(self)
self._lifecycle.mount()
...
await self._lifecycle.unmount()
```

Do **not** instantiate a fresh `AppLifecycle` in `on_unmount`; that would drop mount-time state like `_repl_started`.

## Timer Ownership

Keep timer ownership on `TextualReplApp._slopgotchi_timer` (existing field) to avoid split state and minimize migration risk.

`AppLifecycle` starts/stops that timer via dedicated helper methods.

## Benefits

1. Single lifecycle controller with explicit sequencing.
2. Cleaner app boundary: `mount()` / `unmount()` as the public lifecycle API.
3. Fewer cross-function parameters (`self._app` replaces repeated `app`).
4. Idempotent REPL startup via `_repl_started` guard.
5. Easier to unit test by mocking app/state manager boundaries.

## Implementation Steps

1. Replace free functions in `lifecycle.py` with `AppLifecycle` methods.
2. Update `TextualReplApp` to hold `self._lifecycle: AppLifecycle | None`.
3. In `on_mount`, create + store lifecycle, then call `mount()`.
4. In `on_unmount`, assert lifecycle exists, then call `await unmount()`.
5. Remove old function imports/call sites from `app.py`.
6. Run lint + tests.

## Validation Checklist

- Mount with setup disabled starts worker, logger callback, timer, welcome exactly once.
- Mount with setup enabled starts REPL after setup dismiss callback.
- `_start_repl` remains idempotent.
- Unmount stops timer and saves session.
- No remaining imports of `on_mount`/`on_unmount` from `tunacode.ui.lifecycle`.

## Notes

- Keep lazy import of `SetupScreen` and `show_welcome` to avoid circular dependencies.
- Preserve current behavior where setup dismissal still enters REPL flow (regardless of completion value).
