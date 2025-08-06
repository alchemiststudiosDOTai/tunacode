# ESC Key Handling Bug Investigation
_Started: 2025-08-06 15:27:48_
_Agent: bug-context-analyzer

[1] Found ESC key handler in src/tunacode/ui/keybindings.py:32 - raises KeyboardInterrupt
[2] KeyboardInterrupt from ESC key is caught in src/tunacode/ui/prompt_manager.py:128 and converted to UserAbortError
[3] UserAbortError is handled in src/tunacode/cli/repl.py:277-293 with double-press logic and timeout tracking
[4] Confirmed ESC key handler raises KeyboardInterrupt. Also found escape+enter handler for newline insertion
[5] Integration test confirms flow: ESC → KeyboardInterrupt → UserAbortError → REPL handling
[6] Key observation: There are TWO escape handlers - escape alone and escape,enter. Order matters in prompt_toolkit
[7] Hypothesis: prompt_toolkit may have an escape sequence timeout that affects single ESC handling
[8] Root cause: When escape,enter binding exists, prompt_toolkit waits briefly to see if enter follows escape
