# Fix Application.exit() failed error in ESC keybinding
_Started: 2025-08-09 07:49:17_
_Agent: default

[1] Changed approach: ESC sets special signal __TUNACODE_ESC_SIGNAL__ and validates, approval prompt detects signal and raises UserAbortError
