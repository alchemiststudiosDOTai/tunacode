# Fix unhandled KeyboardInterrupt exception in event loop
_Started: 2025-08-09 03:37:20_
_Agent: default

[1] KeyboardInterrupt raised in keybindings._escape() before reaching our try/catch block
[1] Fixed by changing except KeyboardInterrupt to except UserAbortError - UI framework converts KeyboardInterrupt to UserAbortError
