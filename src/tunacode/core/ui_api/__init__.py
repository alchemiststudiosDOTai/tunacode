"""UI-specific adapters that add behavior or translation for the UI layer.

`tunacode.ui` should import canonical shared modules such as `configuration`,
`constants`, `types`, and `utils` directly. This package exists only for the
small set of UI-facing adapters that still add behavior on top of lower layers.

Dependency direction: ui -> core.ui_api -> (configuration/tools/infrastructure)
"""
