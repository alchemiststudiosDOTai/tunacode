"""End-to-end tool tests driven via tmux.

Launches tunacode in a real tmux session, sends prompts, and verifies that each
tool executes by checking tool-specific output or side effects.

These are true system tests -- they exercise the full stack (TUI, agent loop,
tool dispatch, rendering). They require a live API key and tmux.
"""

import os
import shlex
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMUX_BINARY = "tmux"
SESSION_PREFIX = "tunatest"
DEFAULT_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 2
STARTUP_READY_TIMEOUT_SECONDS = 30
STARTUP_POLL_INTERVAL_SECONDS = 0.5
TMUX_HISTORY_LINES = "-10000"
REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_DIR = REPO_ROOT / ".venv"
API_KEY_ENV_VAR = "MINIMAX_API_KEY"
TEST_API_KEY_ENV_VAR = "TUNACODE_TEST_API_KEY"
RUN_TMUX_TESTS_ENV_VAR = "TUNACODE_RUN_TMUX_TESTS"

# ---------------------------------------------------------------------------
# Markers & skip guards
# ---------------------------------------------------------------------------

_missing_tmux = not shutil.which(TMUX_BINARY)
_missing_tmux_env_vars = [
    env_var
    for env_var in (RUN_TMUX_TESTS_ENV_VAR, TEST_API_KEY_ENV_VAR)
    if not os.environ.get(env_var)
]
_missing_tmux_env_reason = (
    "tmux suite is opt-in; set " + ", ".join(_missing_tmux_env_vars)
    if _missing_tmux_env_vars
    else ""
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.tmux,
    pytest.mark.skipif(_missing_tmux, reason="tmux is not installed"),
    pytest.mark.skipif(bool(_missing_tmux_env_vars), reason=_missing_tmux_env_reason),
    pytest.mark.timeout(DEFAULT_TIMEOUT_SECONDS),
]


# ---------------------------------------------------------------------------
# TmuxSession helper
# ---------------------------------------------------------------------------


class TmuxSession:
    """Manage a detached tmux session running tunacode."""

    def __init__(self, name: str, *, working_directory: Path | None = None) -> None:
        self.name = name
        self.working_directory = working_directory

    # -- tmux primitives -----------------------------------------------------

    def _run_tmux(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            [TMUX_BINARY, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"tmux {' '.join(args)} failed (rc={result.returncode}): {result.stderr}"
            )
        return result.stdout

    def start(self) -> None:
        """Create a detached session and launch tunacode inside it."""
        activate = f"source {VENV_DIR / 'bin' / 'activate'}"
        launch = "tunacode"
        if self.working_directory is None:
            shell_cmd = f"{activate} && {launch}"
        else:
            quoted_working_directory = shlex.quote(str(self.working_directory))
            shell_cmd = f"cd {quoted_working_directory} && {activate} && {launch}"
        self._run_tmux("new-session", "-d", "-s", self.name, "-x", "220", "-y", "50", shell_cmd)

        deadline = time.monotonic() + STARTUP_READY_TIMEOUT_SECONDS
        last_output = ""
        while time.monotonic() < deadline:
            output = self.capture()
            last_output = output
            if any(line.lstrip().startswith("│ >") for line in output.splitlines()):
                return
            time.sleep(STARTUP_POLL_INTERVAL_SECONDS)

        raise TimeoutError(
            "Timed out waiting for tunacode tmux session to render the editor prompt.\n"
            f"Last capture:\n{last_output or self.capture()}"
        )

    def kill(self) -> None:
        """Kill the tmux session (ignore errors if already dead)."""
        self._run_tmux("kill-session", "-t", self.name, check=False)

    def send(self, text: str) -> None:
        """Type *text* followed by Enter into the session."""
        self._run_tmux("send-keys", "-t", self.name, text, "Enter")

    def capture(self) -> str:
        """Return pane contents including recent scrollback history."""
        return self._run_tmux("capture-pane", "-t", self.name, "-p", "-S", TMUX_HISTORY_LINES)


@contextmanager
def tmux_session(
    *,
    working_directory: Path | None = None,
) -> Generator[TmuxSession, None, None]:
    """Context manager: spin up a tunacode tmux session, tear it down on exit."""
    name = f"{SESSION_PREFIX}_{uuid.uuid4().hex[:8]}"
    session = TmuxSession(name, working_directory=working_directory)
    session.start()
    try:
        yield session
    finally:
        session.kill()


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


def wait_for_capture(
    session: TmuxSession,
    predicate: Callable[[str], bool],
    *,
    description: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Poll the pane until *predicate* matches. Returns captured output."""
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        output = session.capture()
        last_output = output
        if predicate(output):
            return output
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Timed out after {timeout}s waiting for {description}.\n"
        f"Last capture:\n{last_output or session.capture()}"
    )


def wait_for_text(
    session: TmuxSession,
    needle: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Poll the pane until *needle* appears. Returns captured output."""
    return wait_for_capture(
        session,
        lambda output: needle in output,
        description=f"{needle!r} in pane",
        timeout=timeout,
    )


def wait_for_all_text(
    session: TmuxSession,
    *needles: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Poll the pane until all *needles* appear together."""
    joined = ", ".join(repr(needle) for needle in needles)
    return wait_for_capture(
        session,
        lambda output: all(needle in output for needle in needles),
        description=f"all of [{joined}] in pane",
        timeout=timeout,
    )


def wait_for_condition(
    predicate: Callable[[], bool],
    *,
    description: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Poll until *predicate* returns True."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out after {timeout}s waiting for {description}.")


# ---------------------------------------------------------------------------
# Tests -- one per tool
# ---------------------------------------------------------------------------


def test_bash_tool() -> None:
    """bash tool: run a command and verify rendered stdout."""
    marker = f"hello-{uuid.uuid4().hex[:8]}"
    with tmux_session() as s:
        s.send(
            f"You MUST call the bash tool. Run: printf {marker}. Do not answer until the tool runs."
        )
        output = wait_for_all_text(s, "stdout:", marker)
        assert marker in output, f"Expected {marker!r} in output:\n{output}"


def test_read_file_tool(tmp_path: Path) -> None:
    """read_file tool: read a temp file and verify its unique contents."""
    target = tmp_path / f"tunatest_read_{uuid.uuid4().hex[:8]}.txt"
    marker = f"read-marker-{uuid.uuid4().hex}"
    target.write_text(f"alpha\n{marker}\nomega\n")

    with tmux_session() as s:
        s.send(
            f"You MUST call the read_file tool. Read {target}. Do not answer until the tool runs."
        )
        output = wait_for_text(s, marker)
        assert marker in output, f"Expected {marker!r} in output:\n{output}"


def test_write_file_tool() -> None:
    """write_file tool: create a temp file and verify it on disk."""
    target = Path(f"/tmp/tunatest_write_{uuid.uuid4().hex[:8]}.txt")
    content_marker = f"hello-from-tunacode-{uuid.uuid4().hex[:8]}"
    try:
        with tmux_session() as s:
            s.send(
                f"You MUST call the write_file tool. Create {target} with content "
                f'"{content_marker}". Do not answer until the tool runs.'
            )
            wait_for_condition(
                lambda: target.exists() and content_marker in target.read_text(),
                description=f"{target} to contain {content_marker!r}",
            )
            assert content_marker in target.read_text(), (
                f"File contents do not contain marker: {target.read_text()!r}"
            )
    finally:
        target.unlink(missing_ok=True)


def test_hashline_edit_tool(tmp_path: Path) -> None:
    """hashline_edit tool: read then edit a pre-created file."""
    target = tmp_path / f"tunatest_edit_{uuid.uuid4().hex[:8]}.txt"
    original_line = "color = red"
    expected_line = "color = blue"
    try:
        target.write_text(original_line)
        with tmux_session() as s:
            s.send(
                "You MUST call read_file, then hashline_edit. "
                f"Read {target}, then change 'color = red' to 'color = blue'. "
                "Do not answer until both tools run."
            )
            wait_for_condition(
                lambda: target.exists() and expected_line in target.read_text(),
                description=f"{target} to contain {expected_line!r}",
            )
            updated = target.read_text()
            assert expected_line in updated, f"Expected {expected_line!r} in:\n{updated}"
    finally:
        target.unlink(missing_ok=True)


def test_discover_tool() -> None:
    """discover tool: search for a known tool implementation and verify structured output."""
    with tmux_session() as s:
        s.send(
            "You MUST call the discover tool. Query: write_file tool implementation. "
            "Do not answer until the tool runs."
        )
        output = wait_for_all_text(s, "scanned:", "write_file.py")
        assert "scanned:" in output, f"Expected 'scanned:' stats in discover output:\n{output}"


def test_web_fetch_tool() -> None:
    """web_fetch tool: fetch example.com and verify success or tool-level failure output."""
    url = "https://example.com/"
    with tmux_session() as s:
        s.send(f"You MUST call the web_fetch tool. Fetch {url}. Do not answer until the tool runs.")
        output = wait_for_capture(
            s,
            lambda pane: f"url: {url}" in pane
            and ("example domain" in pane.lower() or f"failed to connect to {url}" in pane.lower()),
            description="web_fetch result or connection error",
        )
        assert f"url: {url}" in output, f"Expected web_fetch params for {url}:\n{output}"
        assert (
            "example domain" in output.lower() or f"failed to connect to {url}" in output.lower()
        ), f"Expected fetched content or connection error for {url}:\n{output}"


def test_loaded_skill_is_used_via_absolute_referenced_path(tmp_path: Path) -> None:
    """Load a local skill in tmux, then verify the agent uses its referenced file."""
    skill_name = "tmux-e2e-skill"
    skill_description = "TMUX system test skill"
    token = f"TMUX_SKILL_TOKEN_{uuid.uuid4().hex[:8]}"
    skill_dir = tmp_path / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    token_path = skill_dir / "token.txt"
    skill_path = skill_dir / "SKILL.md"

    token_path.write_text(token, encoding="utf-8")
    skill_path.write_text(
        "\n".join(
            [
                "---",
                f"name: {skill_name}",
                f"description: {skill_description}",
                "---",
                "",
                "# TMUX E2E Skill",
                "",
                "When the user asks for the tmux skill token, you must follow this workflow:",
                "1. Read [token.txt](token.txt).",
                "2. Reply with the exact token from that file.",
                '3. Include the sentence "This skill is loaded and being used."',
                "4. Do not guess if you have not read the file.",
            ]
        ),
        encoding="utf-8",
    )

    with tmux_session(working_directory=tmp_path) as s:
        s.send(f"/skills {skill_name}")
        load_output = wait_for_text(s, f"Loaded skill: {skill_name}")
        assert skill_description in load_output, (
            f"Expected skill description in load output:\n{load_output}"
        )

        s.send("What is the tmux skill token? Use the loaded skill and do not guess.")
        tool_output = wait_for_text(s, "token.txt")
        assert "token.txt" in tool_output, f"Expected token file read in output:\n{tool_output}"

        final_output = wait_for_all_text(s, token, "This skill is loaded and being used.")
        assert token in final_output, f"Expected token in output:\n{final_output}"
