# Debug persistent KeyboardInterrupt in event loop
_Started: 2025-08-09 03:40:31_
_Agent: default

[1] KeyboardInterrupt raised in keybindings before reaching session.prompt_async() - need different approach
[1] Fixed by using event.app.exit(exception=KeyboardInterrupt) instead of raise KeyboardInterrupt()
