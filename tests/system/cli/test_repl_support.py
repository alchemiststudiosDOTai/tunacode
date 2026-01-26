from __future__ import annotations

from tunacode.constants import MAX_CALLBACK_CONTENT

from tunacode.ui import repl_support

DIAGNOSTICS_LINE: str = "Error (line 10): type mismatch"
FILLER_UNIT: str = "x"
NEWLINE: str = "\n"


def test_truncate_for_safety_preserves_diagnostics_block() -> None:
    diagnostics_block: str = (
        f"{repl_support.DIAGNOSTICS_BLOCK_START}{NEWLINE}"
        f"{DIAGNOSTICS_LINE}{NEWLINE}"
        f"{repl_support.DIAGNOSTICS_BLOCK_END}{NEWLINE}"
    )
    overflow_length: int = MAX_CALLBACK_CONTENT + len(diagnostics_block)
    filler: str = FILLER_UNIT * overflow_length
    content: str = f"{diagnostics_block}{filler}"

    truncated: str | None = repl_support._truncate_for_safety(content)

    assert truncated is not None
    assert truncated.startswith(diagnostics_block)
    assert DIAGNOSTICS_LINE in truncated
    assert truncated.endswith(repl_support.CALLBACK_TRUNCATION_NOTICE)
